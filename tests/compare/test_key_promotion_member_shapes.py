"""A key that IS a json object and holds a member of the wrong shape.

**The generalisation, and it is the subject of this file.** Every guard written
for the last round of this fault validated the document's *root* and nothing
below it: `key_draft_store._json_object`, `fetch_repo._pinned_commit` and
`promote_key._object` each confirm "this is an object" and then hand it to
callers that subscript its members. So a key that really is an object, holding
`findings: "xy"`, crashed exactly where it had before -- the guard moved the
traceback one frame and changed nothing else.

`refusals` is where that shows, because it is the function every caller of a
hand-edited key reaches: `_malformed_entries` iterated the string and `.get` on
a character raised, `_miscounted` called `len(5)`, and `_pin_refusals` called
`len()` on an int. All three ran *before* `check_key`, which already refuses
every one of these by name. The fix is an ordering one, so the assertion with
teeth is not "it did not crash" but **the sentence reported is the scorer's
own** -- asked of the scorer here rather than transcribed, so the two cannot
drift.

What a document that is not an object at all does is `test_promote_key_wrong_shape.py`,
the root guard one layer up. The same key through the command that publishes one
is `test_promote_key_member_shapes.py`. The five content rules are
`test_key_promotion_refusals.py`; the missing-field and stale-count rules are
`test_key_promotion_shape.py`.

Nothing here touches the filesystem: `refusals` is a pure function over two
documents, and the fixtures build both.
"""

import pytest
from ast_scan import get_call_keys, parse
from conftest import SRC_DIR
from drafted_key_fixtures import fit_key, fit_pin, reported, scorer_sentence
from keys.key_promotion import refusals

# Every way a hand edit leaves `findings` something other than a list of
# entries. Each one is already refused by name at score time, which is what
# makes "ask the scorer first" a complete answer rather than a reordering that
# moves the crash somewhere else.
MALFORMED_FINDINGS = {
    "a string": "xy",
    "a list of numbers": [1, 2],
    "null": None,
    "a list holding null": [None],
}
FINDINGS_IDS = list(MALFORMED_FINDINGS)
FINDINGS_SHAPES = list(MALFORMED_FINDINGS.values())

# `expected_surfaces` is not a field `check_key` reads, so it reaches
# `_miscounted` and is the one member below that the scorer does not speak for.
A_SCALAR = 5
COUNTED_AS_NONE = "holds 0"

# What a hand edit leaves in a pin where a string belongs. Not "what is not a
# commit": the same three shapes break every typed field, which is what lets the
# table below sweep the *fields* rather than one field's values.
NOT_A_STRING = {"an int": 12345, "null": None, "a list": ["c" * 40]}
PIN_IDS = list(NOT_A_STRING)
PIN_SHAPES = list(NOT_A_STRING.values())

# Every pin field `_pin_refusals` checks the type of. This table held one of
# them, in this change, over this function -- and `upstream_url`, two lines
# further down the same body, went on reaching `.startswith` on an int and
# escaping as an `AttributeError` through all three key routes and
# `promote_key.py`. It is swept as a pair now, and the derivation guard below is
# what stops a third field being missed the same way.
TYPED_PIN_FIELDS = ("upstream_commit", "upstream_url")

# The module the guard reads the fields off, rather than trusting the tuple above.
KEY_PROMOTION_SOURCE = SRC_DIR / "keys" / "key_promotion.py"

# A second fault, so "only the scorer's refusal is reported" is a claim about
# ordering and not about there being nothing else wrong.
WRONG_COUNT = 7

# The shape used where the test is not about which shape it is.
ONE_OF_THEM = MALFORMED_FINDINGS["a string"]


def key_whose_findings_are(shape: object) -> dict:
    """A fit key with `findings` replaced by something that is not a list of entries."""
    return {**fit_key(), "findings": shape}


# --- findings: the member every later check walks into --------------------------

@pytest.mark.parametrize("shape", FINDINGS_SHAPES, ids=FINDINGS_IDS)
def test_a_wrong_shaped_findings_is_reported_rather_than_raised(shape: object) -> None:
    """The fault itself: a key that is an object and whose entries are not entries."""
    assert reported(key_whose_findings_are(shape)) != []


@pytest.mark.parametrize("shape", FINDINGS_SHAPES, ids=FINDINGS_IDS)
def test_the_sentence_reported_is_the_scorers_own(shape: object) -> None:
    """Why the fix is an ordering and not a fourth guard: the scorer already names this.

    Equality, and to a list of one: a second copy of these rules in
    `key_promotion` is what the reordering exists to avoid, so what comes back
    has to be `check_key`'s own words and nothing beside them.
    """
    key = key_whose_findings_are(shape)
    assert reported(key) == [scorer_sentence(key)]


@pytest.mark.parametrize("shape", FINDINGS_SHAPES, ids=FINDINGS_IDS)
def test_the_scorer_refuses_every_one_of_these_by_name(shape: object) -> None:
    """Non-vacuity for the reordering: asking the scorer first only works if it answers."""
    assert scorer_sentence(key_whose_findings_are(shape))


def test_nothing_after_the_scorers_refusal_is_run() -> None:
    """A key with a second, ordinary fault still reports one sentence.

    `_miscounted` would report the stale count too -- but it reads the member
    that is broken, so running it at all is the crash this ordering removes.
    """
    key = {**key_whose_findings_are(ONE_OF_THEM), "finding_count": WRONG_COUNT}
    assert reported(key) == [scorer_sentence(key)]


# --- expected_surfaces: the member the scorer does not speak for ----------------

def test_a_scalar_expected_surfaces_is_counted_as_none_rather_than_measured() -> None:
    """`len(5)` was a `TypeError` in the function whose whole job is to say what is wrong."""
    said = reported({**fit_key(), "expected_surfaces": A_SCALAR})
    assert len(said) == 1, said
    assert "expected_surfaces" in said[0] and COUNTED_AS_NONE in said[0]


def test_a_real_list_of_surfaces_is_still_counted() -> None:
    """The off position for the count: a list of two is two, not zero."""
    key = fit_key()
    doubled = {**key, "expected_surfaces": key["expected_surfaces"] * 2,
               "expected_surface_count": 2}
    assert reported(doubled) == []


# --- the pin: the same fault, in the other hand-edited file ---------------------

@pytest.mark.parametrize("field", TYPED_PIN_FIELDS)
@pytest.mark.parametrize("shape", PIN_SHAPES, ids=PIN_IDS)
def test_a_pin_field_that_is_not_a_string_is_refused_by_name(field: str,
                                                             shape: object) -> None:
    """`len()` on an int and `.startswith` on null, in the file a human types into."""
    said = reported(fit_key(), {**fit_pin(), field: shape})
    assert len(said) == 1, said
    assert field in said[0]


def test_the_table_sweeps_every_pin_field_the_refusals_name_for_themselves() -> None:
    """Read off the function, so the next typed field cannot be missed as `upstream_url` was.

    `GRADED_PIN_FIELDS` is reached through the constant rather than by a literal
    key, and is a falsy test no shape can crash -- so what this scan returns is
    exactly the set of fields whose *type* is read, which is exactly the set the
    table has to cover.
    """
    read_by_name = get_call_keys(parse(KEY_PROMOTION_SOURCE), "pin")
    assert read_by_name == set(TYPED_PIN_FIELDS)


# --- the off position everything above rests on ---------------------------------

def test_a_fit_key_and_pin_are_refused_for_nothing() -> None:
    """Without it, a `refusals` that reported something about everything would pass."""
    assert refusals(fit_key(), fit_pin()) == []
