"""Which source a derived name is attributed to when two of them reach it.

`f"{question} {page}"` really does derive from both. The artifact has room for
one, so `_source_within` takes the lowest surface id -- not because the lowest
is more correct than the highest, neither is, but because rule 10 says the same
repository must produce the same findings.json twice. Any rule that read the
*order* the names were met in would not.

Two ways that order could leak in, one test each: the order the names are
written in the expression, and the order the seed map happened to be built in.
Both are varied here while the answer is held fixed.

The last test says the ids are compared as text, so a source on line 10 sorts
before one on line 2. That is arbitrary. It is also stable, and stable is the
whole of what was asked for -- recorded here so a reader meets it as a decision
rather than as a surprise in a diff.
"""

import ast

from artifacts.surface import DATA_SOURCE, Surface
from parsing.languages import PYTHON
from parsing.taint_propagation import propagate

FILE = "main.py"

# Two different data sources with two different names, so the ids differ in more
# than the line and a reader can see which is lower without counting characters.
CHAT_SOURCE_NAME = "st.chat_input"
UPLOAD_SOURCE_NAME = "st.file_uploader"

CHAT_LINE = 1
UPLOAD_LINE = 2

# One value mentioning both tainted names, written each way round.
BOTH_MENTIONED = 'combined = f"{question} {upload}"\n'
MENTIONED_THE_OTHER_WAY = 'combined = f"{upload} {question}"\n'

DERIVED = "combined"


def source(name: str, line: int) -> Surface:
    """One data source, as the extractor would have reported it."""
    return Surface(DATA_SOURCE, name, FILE, line, PYTHON, "detected by test")


CHAT_SOURCE = source(CHAT_SOURCE_NAME, CHAT_LINE)
UPLOAD_SOURCE = source(UPLOAD_SOURCE_NAME, UPLOAD_LINE)


def attributed(snippet: str, seeds: dict[str, Surface]) -> Surface:
    """The source `combined` is attributed to after propagating the given seeds."""
    return propagate(ast.parse(snippet).body, seeds)[DERIVED]


def test_a_value_mentioning_two_sources_cites_the_lower_surface_id() -> None:
    """The rule itself: of the two sources reaching `combined`, the lower id is recorded."""
    assert attributed(BOTH_MENTIONED, {"question": CHAT_SOURCE, "upload": UPLOAD_SOURCE}) \
        == CHAT_SOURCE


def test_writing_the_two_names_the_other_way_round_changes_nothing() -> None:
    """Reading the first name met would answer `upload` here and `question` above."""
    assert attributed(MENTIONED_THE_OTHER_WAY,
                      {"question": CHAT_SOURCE, "upload": UPLOAD_SOURCE}) == CHAT_SOURCE


def test_building_the_seed_map_the_other_way_round_changes_nothing() -> None:
    """A dict keeps insertion order, so a rule that read the seeds in order would differ."""
    assert attributed(BOTH_MENTIONED,
                      {"upload": UPLOAD_SOURCE, "question": CHAT_SOURCE}) == CHAT_SOURCE


def test_the_two_sources_really_are_distinguishable() -> None:
    """The guard for the three tests above: two equal surfaces would pass them all."""
    assert CHAT_SOURCE != UPLOAD_SOURCE
    assert CHAT_SOURCE.id < UPLOAD_SOURCE.id


def test_the_ids_are_compared_as_text_and_not_by_line_number() -> None:
    """A source on line 10 sorts before one on line 2, because an id is a string.

    Arbitrary, and asserted for exactly that reason: it is the one place the
    tie-break stops matching a reader's intuition, and pinning it means the day
    it changes is a red test rather than a findings.json that quietly differs.
    """
    late = source(CHAT_SOURCE_NAME, 10)
    early = source(UPLOAD_SOURCE_NAME, 2)
    assert attributed(BOTH_MENTIONED, {"question": late, "upload": early}) == late
