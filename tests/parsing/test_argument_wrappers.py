"""What a value can be wrapped in and still be a name `argument_names` hands on.

`argument_names` read bare names only, so `agent.invoke({"input": question})` --
the standard LangChain spelling -- passed the value over invisibly. A literal
container and an f-string carry their contents to the callee unchanged, so
`bindings.TRANSPARENT_WRAPPERS` is looked through; a call does not, so it is not.

Two tests do the work: one runs every wrapper spelling a real app writes, and
one asserts that every entry in `TRANSPARENT_WRAPPERS` appears in those
spellings. Without the second, a wrapper added to the constant would ship
untested and look tested.

The plain positional and keyword cases, and the shapes that are *not* looked
through, stay in `test_bindings.py` beside the rest of that module's contract.
This file is the one question of literal wrapping, and
`tests/checks/test_taint_containers.py` is the same question through the check.
"""

import ast

from parsing.bindings import TRANSPARENT_WRAPPERS, argument_names
from test_bindings import first_call

# One tainted name reaching a sink, once per wrapper a real app writes. Each
# case must hand on exactly `question` -- the label says which wrapping is
# under test, so a failure names the shape rather than a line number.
WRAPPER_CASES = {
    "a list": "executor([question])",
    "a tuple": "executor((question,))",
    "a set": "executor({question})",
    "a dict value": 'executor({"input": question})',
    "a dict key": 'executor({question: "value"})',
    "an f-string": 'executor(f"Answer this: {question}")',
    "a starred argument": "executor(*[question])",
    "a double-starred dict": 'executor(**{"input": question})',
    "a nested list of dicts": 'executor(messages=[{"role": "user", "content": question}])',
}

TAINTED_NAME = "question"

# A container holding nothing that could be tainted, and one holding two names.
NO_NAMES = 'executor(["hardcoded", 42])'
TWO_NAMES = "executor([first, second])"

# A call inside a container: the wrapper is looked through, the call is not.
CALL_INSIDE_A_LIST = "executor([build(question)])"


def wrapper_types_in(snippet: str) -> set:
    """The wrapper node types that appear inside one snippet's call."""
    return {type(node) for node in ast.walk(first_call(snippet))
            if isinstance(node, TRANSPARENT_WRAPPERS)}


def test_every_literal_wrapper_hands_the_name_inside_it_on() -> None:
    """Nine spellings of "the value is in there somewhere", and one answer for all of them."""
    found = {label: argument_names(first_call(source))
             for label, source in WRAPPER_CASES.items()}
    assert found == {label: {TAINTED_NAME} for label in WRAPPER_CASES}


def test_every_transparent_wrapper_appears_in_a_case_above() -> None:
    """The guard: a wrapper added to the constant without a case would look tested."""
    covered = set().union(*(wrapper_types_in(source) for source in WRAPPER_CASES.values()))
    assert covered == set(TRANSPARENT_WRAPPERS)


def test_a_container_holding_no_name_hands_nothing_on() -> None:
    """Looking through a wrapper must not make the wrapper itself count as a value."""
    assert argument_names(first_call(NO_NAMES)) == set()


def test_a_container_hands_on_every_name_inside_it() -> None:
    """A list of two names is two values handed over, not one."""
    assert argument_names(first_call(TWO_NAMES)) == {"first", "second"}


def test_the_walk_stops_at_a_call_inside_a_container() -> None:
    """`[build(question)]` hands over what `build` returned, which is not `question`.

    The mechanism, not a verdict on the shape: that this silence is never
    *reported* is an open defect, and `tests/checks/test_taint_defect.py` holds
    it as a strict xfail.
    """
    assert argument_names(first_call(CALL_INSIDE_A_LIST)) == set()
