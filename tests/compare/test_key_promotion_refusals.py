"""Every reason `key_promotion` refuses a draft, one at a time and off again.

`refusals` is the whole of the promotion decision: `promote_key` either moves
two files or repeats what this function returned. So each rule is asserted twice
-- once on a draft that breaks it, once on the same draft with that one fault
repaired -- because a rule that fires on everything and a rule that fires on
nothing both look like a passing test when only one half is written.

Each broken draft is asserted to produce **exactly one** refusal, so a test
cannot pass on some other rule firing instead of the one it names.

The five judgements about the draft's content are here. The two that are about
the document rather than the judgement -- entries missing a field, counts that
disagree with their list -- are `test_key_promotion_shape.py`, because they run
first and stop the five below from being reached at all.

Nothing here touches the filesystem: `refusals` is a pure function over two
documents, and the fixtures build both.
"""

from drafted_key_fixtures import ANCHORED_ENTRY, ENTRY, fit_key, fit_pin
from evaluation.grading import line_window
from keys.key_promotion import (
    ANCHOR_FIELD,
    GRADED_PIN_FIELDS,
    REQUIRED_URL_SCHEME,
    refusals,
)

# A second entry in another file, so reversing the pair breaks the sort order
# without also making the two collidable.
LATER_ENTRY = {**ANCHORED_ENTRY, "id": "K-02", "file": "tools.py", "line": 20}

# The last line a finding could match `ANCHORED_ENTRY` on, taken from the
# scorer's own window rather than from a copy of its arithmetic.
LAST_MATCHING_LINE = line_window(ANCHORED_ENTRY)[1]

# Same file and same risk class, starting on that last line: one finding sits in
# both windows, so it could be counted against both entries.
TOUCHING_ENTRY = {**ANCHORED_ENTRY, "id": "K-02", "line": LAST_MATCHING_LINE}

# The same pair one line further apart, which no single finding reaches.
CLEAR_ENTRY = {**TOUCHING_ENTRY, "line": LAST_MATCHING_LINE + 1}

# An entry whose window is widened by `line_end`, the field a copy of the
# arithmetic in this module used to ignore: its plain line is clear of
# `CLEAR_ENTRY`, and its window is not.
SPANNING_ENTRY = {**ANCHORED_ENTRY, "line_end": CLEAR_ENTRY["line"]}

# A risk class this project scores that `ENTRY` is not, so a pair differing only
# there cannot be double-counted.
OTHER_RISK_CLASS = "LLM01"


def only(said: list[str]) -> str:
    """The one refusal a test expected, failing loudly when another fired beside it."""
    assert len(said) == 1, said
    return said[0]


def pin_without(*fields: str) -> dict:
    """A corrected pin with named fields dropped again."""
    pin = fit_pin()
    for field in fields:
        pin.pop(field)
    return pin


# --- the draft nothing is wrong with ------------------------------------------

def test_a_corrected_draft_is_refused_for_nothing() -> None:
    """The off half of every pair below: without it they could all pass on noise."""
    assert refusals(fit_key(), fit_pin()) == []


# --- the manifest's two human judgements --------------------------------------

def test_a_pin_naming_no_framework_is_refused() -> None:
    """A fetcher cannot know the framework, so a draft's pin does not carry one."""
    assert "framework" in only(refusals(fit_key(), pin_without("framework")))


def test_a_pin_naming_no_language_is_refused() -> None:
    """The other half of the pair, stated on its own so one cannot cover for the other."""
    assert "language" in only(refusals(fit_key(), pin_without("language")))


def test_an_empty_framework_counts_as_naming_none() -> None:
    """A field present but blank pins no judgement, and is refused like an absent one."""
    assert "framework" in only(refusals(fit_key(), fit_pin(framework="")))


def test_a_pin_naming_neither_is_refused_once_and_names_both() -> None:
    """Two missing judgements are one thing to fix, so they are reported together."""
    said = only(refusals(fit_key(), pin_without(*GRADED_PIN_FIELDS)))
    assert "framework" in said and "language" in said


# --- the url the VEX product identity is built from ---------------------------

def test_a_pin_whose_url_is_not_https_is_refused() -> None:
    """`emit_vex.product_iri` joins url and commit unvalidated, so the scheme is checked here."""
    said = only(refusals(fit_key(), fit_pin(upstream_url="http://example.invalid/x")))
    assert REQUIRED_URL_SCHEME in said


def test_a_pin_with_no_url_at_all_is_refused() -> None:
    """The failure this rule exists for: an empty url publishes a product of `@<commit>`."""
    assert REQUIRED_URL_SCHEME in only(refusals(fit_key(), fit_pin(upstream_url="")))


def test_another_https_url_is_not_refused() -> None:
    """The off half: the rule is about the scheme, not about one fixture's url."""
    assert refusals(fit_key(), fit_pin(upstream_url="https://example.invalid/other")) == []


# --- the anchor each entry quotes ---------------------------------------------

def test_an_entry_with_no_anchor_field_is_refused_by_id() -> None:
    """`ENTRY` is the shape the model replies in: no anchor, because it was never asked for one."""
    said = only(refusals(fit_key((ENTRY,)), fit_pin()))
    assert ANCHOR_FIELD in said and ENTRY["id"] in said


def test_an_entry_whose_anchor_is_empty_is_refused() -> None:
    """`key_drafting._anchor` returns "" when the file or line moved, which is the case to catch."""
    blank = {**ANCHORED_ENTRY, ANCHOR_FIELD: ""}
    assert ANCHOR_FIELD in only(refusals(fit_key((blank,)), fit_pin()))


def test_the_refusal_counts_the_entries_it_found() -> None:
    """Two unanchored entries are reported as two, so a reader knows how much to fix."""
    second = {**ENTRY, "id": "K-02", "file": "tools.py", "line": 20}
    said = only(refusals(fit_key((ENTRY, second)), fit_pin()))
    assert said.startswith("2 entries") and "K-02" in said


# --- the order two revisions of a key are diffed in ---------------------------

def test_entries_out_of_the_documented_order_are_refused() -> None:
    """Sorted by (file, line, id); `key_document` sorts them, so this catches a hand edit."""
    key = {**fit_key((ANCHORED_ENTRY, LATER_ENTRY)),
           "findings": [LATER_ENTRY, ANCHORED_ENTRY]}
    assert "(file, line, id)" in only(refusals(key, fit_pin()))


def test_the_same_two_entries_in_order_are_not_refused() -> None:
    """The off half: two entries are fine, and it is their order that was wrong."""
    assert refusals(fit_key((ANCHORED_ENTRY, LATER_ENTRY)), fit_pin()) == []


# --- two entries one finding could answer twice -------------------------------

def test_two_entries_within_the_line_window_are_refused_by_id() -> None:
    """One finding matching both would read as recall the tool did not earn."""
    said = only(refusals(fit_key((ANCHORED_ENTRY, TOUCHING_ENTRY)), fit_pin()))
    assert f"{ANCHORED_ENTRY['id']} and {TOUCHING_ENTRY['id']}" in said


def test_the_same_pair_one_line_further_apart_is_not_refused() -> None:
    """The off half, one line past the scorer's window: no finding reaches both."""
    assert refusals(fit_key((ANCHORED_ENTRY, CLEAR_ENTRY)), fit_pin()) == []


def test_two_touching_entries_of_different_risk_classes_are_not_refused() -> None:
    """The join is (file, owasp_id, line), so two classes at one line answer two questions."""
    other = {**TOUCHING_ENTRY, "owasp_id": OTHER_RISK_CLASS}
    assert refusals(fit_key((ANCHORED_ENTRY, other)), fit_pin()) == []


def test_an_entry_whose_line_end_reaches_the_next_one_is_refused() -> None:
    """`line_end` widens the window in the scorer, so it has to widen it here too."""
    said = only(refusals(fit_key((SPANNING_ENTRY, CLEAR_ENTRY)), fit_pin()))
    assert f"{SPANNING_ENTRY['id']} and {CLEAR_ENTRY['id']}" in said


def test_the_same_pair_without_that_line_end_is_not_refused() -> None:
    """The off half: it is the span that collides, not the two lines on their own."""
    assert refusals(fit_key((ANCHORED_ENTRY, CLEAR_ENTRY)), fit_pin()) == []
