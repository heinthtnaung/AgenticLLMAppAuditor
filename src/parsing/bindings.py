"""Records which name a call's result was bound to, within one file.

A surface says a call happened at a line; it does not say what the result was
called afterwards. Tracing an untrusted value to where it is used needs that
missing half, and it is the same half that says whether `x.load()` is a
document loader or an unrelated object.

Deliberately one file at a time. Following a value across modules, and then
across the package boundary, is an unbounded problem; this stays inside what a
single syntax tree can prove.
"""

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class Binding:
    """One name, and the line of the call whose result it holds."""

    name: str
    line: int


def _bound_names(target: ast.AST) -> list[str]:
    """Return the plain names a single assignment target binds."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [e.id for e in target.elts if isinstance(e, ast.Name)]
    return []


def _record(bindings: dict, names: list[str], value: ast.AST) -> None:
    """Bind each name to the line of the call it holds, ignoring non-calls."""
    if not isinstance(value, ast.Call):
        return
    for name in names:
        bindings[name] = Binding(name, value.lineno)


# A binding belongs to the function that made it. Walking a whole module at
# once conflates them: an app may bind `cursor` inside several functions, and a
# module-wide view would report the last one for every use.
SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)

# A class body is not a scope its methods share: two methods binding the same
# name are two bindings, so the class is excluded from the module's top level
# and its methods are picked up as scopes in their own right.
TOP_LEVEL_EXCLUDED = SCOPE_NODES + (ast.ClassDef,)


@dataclass(frozen=True)
class Scope:
    """One scope's statements and the names it binds from a call.

    The two travel together because reading either without the other is the
    bug this type exists to prevent: matching one scope's names against another
    scope's code.
    """

    body: list[ast.stmt]
    bindings: dict[str, Binding]


def _scope_bodies(tree: ast.Module) -> list[list[ast.stmt]]:
    """Return each function's body, plus the module's own top level.

    A nested function is walked with its parent, which over-approximates in the
    direction that costs nothing here: a closure really can see the enclosing
    name.
    """
    functions = [n for n in ast.walk(tree) if isinstance(n, SCOPE_NODES)]
    top_level = [n for n in tree.body if not isinstance(n, TOP_LEVEL_EXCLUDED)]
    return [top_level] + [f.body for f in functions]


def _nodes_in(body: list[ast.stmt]) -> list[ast.AST]:
    """Every node inside one scope's own statements, and no other scope's."""
    return [node for statement in body for node in ast.walk(statement)]


def _record_binding(bindings: dict, node: ast.AST) -> None:
    """Record whatever names one assignment statement binds."""
    if isinstance(node, ast.Assign):
        for target in node.targets:
            _record(bindings, _bound_names(target), node.value)
    elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)):
        _record(bindings, _bound_names(node.target), node.value)


def _bindings_in(body: list[ast.stmt]) -> dict[str, Binding]:
    """Map the names one scope binds from a call to the line of that call."""
    bindings: dict[str, Binding] = {}
    for node in _nodes_in(body):
        _record_binding(bindings, node)
    return bindings


def scoped_call_bindings(tree: ast.Module) -> list[Scope]:
    """Return each scope with the names it can see, so a name is read where it was bound.

    **A function sees the module's names too**, which is how Python reads and
    was the trace's largest silent miss. `client = OpenAI()` at module level with
    the source and the call inside a function -- the shape of every script-style
    LLM app -- produced no finding *and no probe*: the sink was bound in one
    scope and the value in another, and nothing said so.

    Module names go underneath the scope's own, and a name the function writes
    to *at all* shadows the module's -- not merely one bound to a call, which
    is all `_bindings_in` records. Reading it that way once meant
    `question = "a literal"` inside a function did not shadow a module-level
    source, and a string constant was reported as untrusted input.
    """
    module_body, *function_bodies = _scope_bodies(tree)
    module = _bindings_in(module_body)
    scopes = [Scope(module_body, module)]
    scopes += [Scope(body, _visible_in(body, module)) for body in function_bodies]
    return [scope for scope in scopes if scope.bindings]


def _assigned_anywhere(body: list[ast.stmt]) -> set[str]:
    """Every name this body writes to, however it writes it.

    Any store counts -- an assignment, a loop variable, a `with ... as`, a
    walrus -- because all of them make the name local, and a local name is not
    the module's whatever it was assigned from. `_bindings_in` records only
    names bound to a *call*, so asking it instead would let
    `question = "a literal"` fail to shadow a module-level source and report a
    string constant as untrusted input.
    """
    return {node.id for statement in body for node in ast.walk(statement)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)}


def _visible_in(body: list[ast.stmt], module: dict) -> dict:
    """The names one function scope can see: its own, over the module's it does not shadow."""
    shadowed = _assigned_anywhere(body)
    inherited = {name: binding for name, binding in module.items() if name not in shadowed}
    return {**inherited, **_bindings_in(body)}


# What a value can be wrapped in and still be the value that was handed over.
# A literal container and an f-string carry their contents to the callee
# unchanged; a call does not, which is why one is absent from this list.
TRANSPARENT_WRAPPERS = (ast.List, ast.Tuple, ast.Set, ast.Dict, ast.JoinedStr,
                        ast.FormattedValue, ast.Starred)


def argument_names(call: ast.Call) -> set[str]:
    """Return the plain names passed to a call, through any literal wrapping.

    `agent.invoke({"input": question})` and `create(messages=[{"content": c}])`
    hand the value over as surely as `agent.invoke(question)` does; seeing bare
    names only meant a dict hid it, and the miss was silent rather than a probe.

    **A nested call is deliberately not walked.** In `agent.invoke(build(x))`
    the value handed to the agent is whatever `build` returned, and calling that
    `x` would be a different claim than the one this check makes. That shape is
    a recorded hole, not a decided silence -- see `tests/checks/test_taint_defect.py`.
    """
    given = list(call.args) + [keyword.value for keyword in call.keywords]
    return {name for argument in given for name in _names_within(argument)}


def _names_within(node: ast.expr) -> set[str]:
    """Every bare name this expression hands on, looking through literal wrappers only."""
    if isinstance(node, ast.Name):
        return {node.id}
    if not isinstance(node, TRANSPARENT_WRAPPERS):
        return set()
    return {name for child in ast.iter_child_nodes(node)
            if isinstance(child, ast.expr) for name in _names_within(child)}


def receiver_name(call: ast.Call) -> str:
    """Return the local name whose object is called: the callee for `f(x)`, `obj` for `obj.m(x)`.

    A deeper chain answers "": in `a.b.c(x)` the receiver is the *value* of
    `a.b`, which is not a local name this file bound and so cannot be matched
    against one.
    """
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id
    return ""


def method_name(call: ast.Call) -> str:
    """Return the method called on that name, or "" when the call is a bare name.

    Kept apart from the receiver because they answer different questions:
    *which object* is being used, and *what is being asked of it*. A caller
    that cares only about the object should not have to know about methods.
    """
    return call.func.attr if isinstance(call.func, ast.Attribute) else ""
