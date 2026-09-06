"""Extending a scope's tainted names to everything derived from them.

The trace used to taint a name only where it was bound *at* a data source, so a
chain died at its second hop: `response = requests.get(url)` was followed and
`page_text = response.text` was not. `propagate` closes that, and this file pins
it directly -- one scope's statements and a seed map, with no repository, no
surfaces document and no check wrapped around it.

Three concerns, in the order they appear below: how far a chain is followed,
which assignment targets carry the taint onward, and that the fixpoint stops.
The last is the reason several tests here look trivial. `propagate` loops until a
pass adds nothing, so `x = f(x)`, two names assigned from each other, and an
assignment inside a loop are the three shapes that would spin forever if a pass
ever re-reported a name it had already tainted. Running them *is* the assertion:
a regression makes this file hang rather than fail, and there is no honest way
to test termination that does not run the loop.

Every tree is written here rather than read from a repository, and what that
costs is what every synthetic tree costs: these are the shapes someone thought
of. The real file that breaks the trace is by definition one nobody wrote down.
"""

import ast

from artifacts.surface import DATA_SOURCE, Surface
from parsing.languages import PYTHON
from parsing.taint_propagation import propagate

FILE = "main.py"

# An outbound http read: a real spelling from `detectors/detector_names.py`, so
# the seed is the kind of surface the extractor would actually have reported.
SOURCE_NAME = "requests.get"
SOURCE_LINE = 1

# The second hop the trace used to die at, and the one it dies at now.
TWO_HOP = "page_text = response.text\n"

THREE_HOP = ('page_text = response.text\n'
             'summary = page_text[:200]\n'
             'message = f"Summarise this: {summary}"\n')

# `summary` is written on the line *above* the one that taints `detail`. A
# single top-to-bottom pass never comes back to it.
ASSIGNED_ABOVE = ('summary = detail\n'
                  'detail = raw_page\n')

# The three shapes that would not terminate without the "only ever add" rule.
ASSIGNED_FROM_ITSELF = "payload = decode(payload)\n"

MUTUALLY_ASSIGNED = ('first = second\n'
                     'second = first\n')

INSIDE_A_LOOP = ('while more_pages:\n'
                 '    collected = chunk\n'
                 '    chunk = collected\n')


def source(line: int = SOURCE_LINE) -> Surface:
    """One data source, as the extractor would have reported it."""
    return Surface(DATA_SOURCE, SOURCE_NAME, FILE, line, PYTHON, "detected by test")


def spread(snippet: str, *seed_names: str) -> dict[str, Surface]:
    """Propagate one source's taint through a snippet, seeded at the given names."""
    return propagate(ast.parse(snippet).body, {name: source() for name in seed_names})


def tainted_names(snippet: str, *seed_names: str) -> set[str]:
    """The names a snippet leaves tainted, the seeds included."""
    return set(spread(snippet, *seed_names))


def test_a_name_derived_from_a_seed_is_tainted() -> None:
    """`page_text = response.text` -- the second hop, and the whole point of the module."""
    assert tainted_names(TWO_HOP, "response") == {"response", "page_text"}


def test_a_three_hop_chain_is_followed_to_its_end() -> None:
    """Read, slice, format: the shape of real code between a source and a model."""
    assert tainted_names(THREE_HOP, "response") == {
        "response", "page_text", "summary", "message"}


def test_a_derived_name_carries_the_source_it_came_from() -> None:
    """The finding is anchored on the source, so the last hop must still name the first."""
    assert spread(THREE_HOP, "response")["message"] == source()


def test_a_name_assigned_above_the_line_that_taints_it_is_still_reached() -> None:
    """The fixpoint, not one pass in source order.

    `summary = detail` is written before `detail` is tainted. A single
    top-to-bottom read taints `detail` on line 2 and never returns to line 1, so
    `summary` would come out clean -- which is what a loop body, a branch, or a
    helper defined above its caller looks like to this function.
    """
    assert tainted_names(ASSIGNED_ABOVE, "raw_page") == {"raw_page", "detail", "summary"}


def test_a_tuple_unpack_taints_every_name_it_binds() -> None:
    """Both halves of `head, tail = payload` hold part of an untrusted value."""
    assert tainted_names("head, tail = payload\n", "payload") == {"payload", "head", "tail"}


def test_a_list_unpack_taints_every_name_it_binds() -> None:
    """`[head, tail] = payload` is the same unpack in the other spelling."""
    assert tainted_names("[head, tail] = payload\n", "payload") == {"payload", "head", "tail"}


def test_an_attribute_target_taints_nothing() -> None:
    """`self.text = payload` binds no name this trace can match later.

    A documented limit of the trace, not of this function: every later use is
    `self.text`, and the trace reads bare names. The value is genuinely carried
    and genuinely lost, which is why it is asserted rather than assumed.
    """
    assert tainted_names("self.text = payload\n", "payload") == {"payload"}


def test_a_name_from_an_untainted_expression_stays_clean() -> None:
    """Nothing tainted is mentioned, so nothing new is tainted -- the negative half."""
    assert tainted_names("greeting = build_greeting()\n", "payload") == {"payload"}


def test_a_scope_with_no_statements_returns_exactly_its_seeds() -> None:
    """Nothing to extend is a real answer, not an error."""
    assert tainted_names("", "payload") == {"payload"}


def test_the_seed_map_is_left_unchanged() -> None:
    """A pure function: `checks/taint.py` reuses the map it passed in."""
    seeds = {"response": source()}
    propagate(ast.parse(TWO_HOP).body, seeds)
    assert seeds == {"response": source()}


def test_a_name_assigned_from_itself_terminates() -> None:
    """`payload = decode(payload)` adds nothing, because `payload` is already tainted.

    The pass that would otherwise repeat forever. This test hangs rather than
    fails if the "only ever add" rule is lost, which is the honest shape of a
    termination property.
    """
    assert tainted_names(ASSIGNED_FROM_ITSELF, "payload") == {"payload"}


def test_two_names_assigned_from_each_other_terminate() -> None:
    """`first = second` beside `second = first`: one new name, then a pass that adds none."""
    assert tainted_names(MUTUALLY_ASSIGNED, "first") == {"first", "second"}


def test_an_assignment_inside_a_loop_terminates() -> None:
    """A loop body is read like any other statement, and read again until it settles."""
    assert tainted_names(INSIDE_A_LOOP, "chunk") == {"chunk", "collected"}
