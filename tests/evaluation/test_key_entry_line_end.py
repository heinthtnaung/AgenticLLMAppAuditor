"""The far edge of the match window: optional, nullable, and still typed.

**The same crash, on the same line of code, one field along.** `line` was typed
and `line_end` was not, and `grading.line_window` adds the tolerance to
whichever of them it ends up holding -- so `line_end: "20"` was the identical
`TypeError`, reached from the scoring path and from promotion, for as long as
`line` alone was checked.

**And the boolean is worse here than it is for `line`.** Measured, with the
entry anchored at line 7:

    line_end "20"  -> TypeError: can only concatenate str (not "int") to str
    line_end [20]  -> TypeError: can only concatenate list ...
    line_end true  -> no crash at all. line_window returns (7, 4)

A window whose start is *after* its end makes `first <= line <= last` false for
every finding there could ever be, so the entry is unanswerable: it scores as a
**miss the tool earned**, and nothing anywhere says the key was malformed. That
is a wrong number in `evaluation.json` with no traceback and no refusal behind
it, which is why the third section states it as its own claim rather than
leaving it implied by a type check.

**It could not join `TYPED_ENTRY_FIELDS`**, because `_check_entry` subscripts
that map's fields straight after the presence check and `line_end` is genuinely
optional -- `test_key_entry_types.py::test_every_typed_field_is_also_a_required_one`
forbids it, correctly. Hence a second map checked only when the value is not
None, and hence the second section: absent, `null` and a real int must all still
be accepted, because both drafts this project has ever written carry
`line_end: null`.

Pure dicts throughout. Through promotion it is
`tests/compare/test_key_promotion_entry_types.py`; over the editor's routes,
`tests/web/test_key_entry_types.py`.
"""

from dataclasses import asdict
from pathlib import Path

import pytest

from evaluation.grading import LINE_TOLERANCE, line_window, matches_key
from evaluation.harness import (
    ENTRY_FIELDS, NULLABLE_TYPED_ENTRY_FIELDS, TYPED_ENTRY_FIELDS, check_key)
from evaluation_fixtures import LINE, grading_key, key_entry
from findings_fixtures import static_finding
from grading_key_rules import OPTIONAL_ENTRY_FIELDS
from guarded_read import refusal_from

# Stands in for the path the key was read from; nothing here opens it.
KEY_FILE = Path("grading_keys/an-app.ground_truth.json")

# What a hand edit leaves where the end of a construct belongs.
NOT_A_LINE_END = {"a string": "20", "a list": [20], "a bool": True}
REFUSED_IDS = list(NOT_A_LINE_END)
REFUSED_SHAPES = list(NOT_A_LINE_END.values())

# The end of a construct that really spans lines, and the two ways a key says
# "this one does not". Absent is a third and is its own test, because it is a
# different edit: `null` is written by the producer, absent is an older key.
A_REAL_LINE_END = LINE + 8
MEANS_ONE_LINE = {"null": None, "an int": A_REAL_LINE_END}
ACCEPTED_IDS = list(MEANS_ONE_LINE)
ACCEPTED_SHAPES = list(MEANS_ONE_LINE.values())

# Every line a finding could plausibly sit on, for the claim that an inverted
# window answers none of them. Wide enough to cover the whole of a small file.
EVERY_PLAUSIBLE_LINE = range(1, 40)


def produced(**overrides) -> dict:
    """The produced finding as the artifact holds it: a plain dict, not a record."""
    return asdict(static_finding(**overrides))


def refuse(entry: dict) -> str:
    """Check a key holding this one entry and return the sentence it is refused with."""
    raised = refusal_from(lambda: check_key(grading_key([entry]), KEY_FILE), "check_key")
    assert isinstance(raised, ValueError), (
        f"check_key raised {type(raised).__name__} instead of refusing: {raised}")
    return str(raised)


def without_a_line_end() -> dict:
    """One entry as a key written before the field existed spells it: no `line_end` at all."""
    entry = key_entry()
    del entry["line_end"]
    return entry


# --- the type half --------------------------------------------------------------

@pytest.mark.parametrize("shape", REFUSED_SHAPES, ids=REFUSED_IDS)
def test_a_line_end_that_is_not_a_number_is_refused(shape: object) -> None:
    """The hole itself: typed `line` and untyped `line_end` reach the same arithmetic."""
    assert "line_end" in refuse(key_entry(line_end=shape))


@pytest.mark.parametrize("shape", REFUSED_SHAPES, ids=REFUSED_IDS)
def test_the_refusal_names_the_entry_and_what_it_found(shape: object) -> None:
    """A key with twenty entries is unscannable by eye, so the message points at one."""
    said = refuse(key_entry(line_end=shape))
    assert "findings[0]" in said
    assert type(shape).__name__ in said


# --- the optional half, which the type check may not take away ------------------

@pytest.mark.parametrize("shape", ACCEPTED_SHAPES, ids=ACCEPTED_IDS)
def test_a_line_end_a_producer_really_writes_is_accepted(shape: object) -> None:
    """`null` is the shape of both drafts this project has written; an int is a real span."""
    key = grading_key([key_entry(line_end=shape)])
    assert check_key(key, KEY_FILE) is key


def test_an_entry_with_no_line_end_at_all_is_accepted() -> None:
    """Absent is not null and is checked separately: `entry[field]` on it is a `KeyError`.

    This is the shape that made a second map necessary rather than an entry in
    the first one, so it is asserted rather than assumed.
    """
    key = grading_key([without_a_line_end()])
    assert check_key(key, KEY_FILE) is key


# --- why it is checked at all ---------------------------------------------------

def test_the_window_cannot_take_a_line_end_that_is_text() -> None:
    """Non-vacuity for the refusals: the crash is real, and it is the same `+` as `line`'s."""
    raised = refusal_from(
        lambda: line_window({"line": LINE, "line_end": NOT_A_LINE_END["a string"]}),
        "line_window")
    assert isinstance(raised, TypeError), raised


def test_a_true_line_end_inverts_the_window_instead_of_raising() -> None:
    """The measured silent shape: a start *after* its end, and no exception anywhere."""
    first, last = line_window({"line": LINE, "line_end": True})
    assert (first, last) == (LINE, 1 + LINE_TOLERANCE)
    assert first > last, "the window is inverted, which is the whole fault"


def test_an_entry_with_an_inverted_window_answers_no_finding_at_all() -> None:
    """Why the `bool` clause exists: this scores as a miss the tool earned.

    Every line of a small file, not one: the claim is that the entry is
    unanswerable, and a single probe line could miss by arithmetic instead.
    """
    entry = key_entry(line_end=True)
    assert not any(matches_key(produced(line=line), entry)
                   for line in EVERY_PLAUSIBLE_LINE)


def test_the_same_entry_without_that_boolean_is_answered() -> None:
    """The off position: the finding really would have matched, so the miss is the window's."""
    assert matches_key(produced(), key_entry(line_end=None))


# --- the two maps, and the line between them ------------------------------------

def test_no_field_is_in_both_maps() -> None:
    """They say contradictory things: one requires a value, the other permits `null`."""
    assert set(TYPED_ENTRY_FIELDS) & set(NULLABLE_TYPED_ENTRY_FIELDS) == set()


def test_no_nullable_typed_field_is_a_required_one() -> None:
    """The mirror of `test_every_typed_field_is_also_a_required_one`.

    A required field in this map would be a field the presence check already
    demands and this check then says `null` is fine for -- two rules
    contradicting each other about one field. It belongs in `TYPED_ENTRY_FIELDS`.
    """
    assert set(NULLABLE_TYPED_ENTRY_FIELDS) & set(ENTRY_FIELDS) == set()


def test_every_nullable_typed_field_is_one_the_schema_marks_optional() -> None:
    """Held to `docs/SCHEMAS.md` through `grading_key_rules`, not to the code it checks.

    A list taken from the module under test agrees with it by construction. This
    one is read off the schema, so a field typed here that the schema never
    marked optional is a check stricter than the schema -- as wrong as a looser
    one, and harder to spot because its own tests pass.
    """
    assert set(NULLABLE_TYPED_ENTRY_FIELDS) <= set(OPTIONAL_ENTRY_FIELDS)
