"""Every refusal under `/api/runs` is raised by a name that says which refusal it is.

Two of this router's status codes are the same number. `ALREADY_RUNNING` is 409
because an audit is in flight; `NOT_FAILED` is 409 because the run a caller
asked to forget is finished or still going. **No test that drives the endpoint
can tell those apart**, because a response carries the number and not the name
it was written with -- so swapping one constant for the other is a change that
every behavioural test in this folder passes, and a reader who then followed
`ALREADY_RUNNING` into the delete handler would be told an audit was running
when none was.

So this file reads the source instead. It is the same shape of guard as
`tests/test_no_write_commands.py`: a negative about code, which running the code
cannot show, because a path not taken looks exactly like a path that does not
exist.

**What is asserted is two things, and deliberately not a third.** First, that no
refusal in this router is raised with a bare number -- `status_code=409` names
nothing at all, which is rule 12 and is the state this would decay to. Second,
that each handler raises the constants that belong to it, so the two 409s stay
told apart. What is **not** asserted is which number any constant equals:
`docs/SCHEMAS.md` fixes the codes and the tests that drive the endpoints hold
them, and a second copy of `409` here would be exactly the duplication this file
exists to object to.

`docs/SCHEMAS.md` is where the decision is written down -- "the request is well
formed and the run's *state* refuses it, which is the distinction
`ALREADY_RUNNING` and `SUPERSEDED` already draw" -- and `downloads.py` set the
precedent with `SUPERSEDED`. This is that sentence made executable.

What a text-level guard cannot see: a refusal raised through a helper that takes
the code as an argument, or a constant aliased to another name before use.
Neither is how this module is written, and both would fail the first assertion
below rather than pass silently.

Reads one module with `ast` and imports it for its constants. No request is
driven, no store is opened, nothing is written.
"""

import ast
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no router")

import run_routes                                   # noqa: E402

from ast_scan import parse                          # noqa: E402

# The exception every refusal in this module is raised as.
REFUSAL_CLASS = "HTTPException"
STATUS_KEYWORD = "status_code"

# What counts as a function for the purpose of "which handler raised this".
THE_FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)

# Which constants each handler is entitled to raise. Written as the whole set
# per handler rather than as "the delete route must not say ALREADY_RUNNING":
# the interesting mistake is a *swap*, and a ban on one name would be satisfied
# by a swap to any third one.
REFUSALS_BY_HANDLER = {
    "audit": {"REFUSED", "ALREADY_RUNNING"},
    "one_run": {"NO_SUCH_RUN"},
    "forget_run": {"NO_SUCH_RUN", "NOT_FAILED"},
}

# The two names that are the same number, so a reader of this file knows why the
# guard exists at all. Compared to each other, never to a literal.
THE_TWO_CONFLICTS = ("ALREADY_RUNNING", "NOT_FAILED")

# A floor under the sweep: five raises across the three handlers today. An
# `ast` walk that matched nothing would satisfy every comparison above.
MINIMUM_REFUSALS = 5


def parse_snippet(text: str) -> ast.Module:
    """A planted handler, parsed the same way the router is."""
    return ast.parse(text)


def router_source() -> ast.Module:
    """The router's own syntax tree, read from the file the import resolved to."""
    return parse(Path(run_routes.__file__))


def _status_name(call: ast.Call) -> str:
    """The name a refusal's `status_code=` was written with, or the literal as text."""
    for keyword in call.keywords:
        if keyword.arg != STATUS_KEYWORD:
            continue
        return keyword.value.id if isinstance(keyword.value, ast.Name) \
            else ast.unparse(keyword.value)
    return ""


def _nodes_owned_by(node: ast.AST) -> list[ast.AST]:
    """Everything inside one function, never descending into a function nested in it.

    The handlers are closures inside `register`, so a plain `ast.walk` credits
    every refusal in the module to `register` as well as to the handler that
    raises it -- and a swap between two handlers would then be invisible.
    """
    found: list[ast.AST] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, THE_FUNCTION_NODES):
            continue
        found.append(child)
        found += _nodes_owned_by(child)
    return found


def refusals_in(tree: ast.Module) -> list[tuple[str, str]]:
    """Every refusal raised in the module, as (handler, the name its code was written with)."""
    found: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, THE_FUNCTION_NODES):
            continue
        found += [(node.name, _status_name(call)) for call in _nodes_owned_by(node)
                  if isinstance(call, ast.Call)
                  and getattr(call.func, "id", "") == REFUSAL_CLASS]
    return found


def refusals_by_handler(tree: ast.Module) -> dict[str, set[str]]:
    """The constants each handler raises, keyed by the handler's own name."""
    gathered: dict[str, set[str]] = {}
    for handler, name in refusals_in(tree):
        gathered.setdefault(handler, set()).add(name)
    return gathered


# --- no refusal is raised with a bare number -----------------------------------

def test_every_refusal_names_a_constant_rather_than_a_number() -> None:
    """`status_code=409` names nothing; rule 12, and the state this would decay to."""
    written = [f"{handler}: {name}" for handler, name in refusals_in(router_source())
               if not name.isidentifier()]
    assert written == []


def test_the_sweep_found_the_refusals_this_router_makes() -> None:
    """Non-vacuity: a walk that matched nothing satisfies every comparison here."""
    assert len(refusals_in(router_source())) >= MINIMUM_REFUSALS


# --- and each handler raises the ones that belong to it ------------------------

def test_each_handler_refuses_with_the_constants_that_belong_to_it() -> None:
    """The swap this file exists for: two 409s that no response can tell apart."""
    assert refusals_by_handler(router_source()) == REFUSALS_BY_HANDLER


def test_forgetting_a_run_refuses_a_wrong_status_by_its_own_name() -> None:
    """Named on its own, so the failure reads as what it is rather than as a dict diff."""
    assert "NOT_FAILED" in refusals_by_handler(router_source())["forget_run"]
    assert "ALREADY_RUNNING" not in refusals_by_handler(router_source())["forget_run"]


def test_the_two_names_really_are_the_same_number() -> None:
    """Why a response cannot tell them apart, and therefore why this file is source-level."""
    first, second = (getattr(run_routes, name) for name in THE_TWO_CONFLICTS)
    assert first == second


def test_a_swapped_constant_is_reported_by_name() -> None:
    """Planted: the comparison above is a dict either way, so the swap is shown to be caught."""
    swapped = parse_snippet(
        "def forget_run(run_id):\n"
        "    raise HTTPException(status_code=ALREADY_RUNNING, detail='')\n")
    assert refusals_by_handler(swapped) == {"forget_run": {"ALREADY_RUNNING"}}


def test_a_bare_number_is_reported_as_written() -> None:
    """Planted: the first check is an empty list whether or not the sweep can see a literal."""
    bare = parse_snippet(
        "def forget_run(run_id):\n"
        "    raise HTTPException(status_code=409, detail='')\n")
    assert refusals_in(bare) == [("forget_run", "409")]
