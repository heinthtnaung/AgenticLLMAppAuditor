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


def call_bindings(tree: ast.AST) -> dict[str, Binding]:
    """Map every name bound from a call to that call's line.

    A later binding wins, which is what a reader of the file sees: the name
    refers to whatever it was last assigned before it is used.
    """
    bindings: dict[str, Binding] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                _record(bindings, _bound_names(target), node.value)
        elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)):
            _record(bindings, _bound_names(node.target), node.value)
    return bindings


def argument_names(call: ast.Call) -> set[str]:
    """Return the plain names passed to a call, positionally or by keyword."""
    given = list(call.args) + [k.value for k in call.keywords]
    return {a.id for a in given if isinstance(a, ast.Name)}


def called_name(call: ast.Call) -> str:
    """Return the plain name being called, or "" when it is not a bare name."""
    return call.func.id if isinstance(call.func, ast.Name) else ""
