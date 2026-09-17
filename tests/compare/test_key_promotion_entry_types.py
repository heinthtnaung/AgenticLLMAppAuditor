"""A draft whose entries are all there, and whose `line` is not a number.

**The same fault as `test_key_promotion_member_shapes.py`, one level down.**
That file is about the key's *members*: `findings: "xy"` got past a guard that
validated the root and nothing under it. Asking the scorer first closed that
family and left this one open, because `check_key` walked down to the entries
and stopped at whether the fields were **there**. So the generalisation is not
"the root versus its members" but **a member's presence versus its type**, and
`"line": "4"` -- one quote-pair, in the field a person retypes most -- went on
reaching `_out_of_order`:

    TypeError: '<' not supported between instances of 'int' and 'str'

Reached from all three key routes and from `promote_key.py`, with no PUT
involved: a hand-edited drafted key does it -- and for `id`, no hand edit at
all, since a model reply labelling an entry `1` lands in a draft this same
function then reads. `line_end` is the same fault in the
same arithmetic and is swept here too, with its legal `null`, real int and
absent shapes held at the end -- refusing any of those would make every draft
this project has written unpromotable.

What is asserted is again not "it did not crash". `refusals` asks the scorer
first, and `harness.TYPED_ENTRY_FIELDS` now refuses every shape below by name,
so the sentence that comes back must be `check_key`'s own -- asked of
`check_key` here rather than transcribed, so the two cannot drift.

The scorer's own half is `tests/evaluation/test_key_entry_types.py`, and the
same key reaching it from disk is `tests/cli/test_evaluate_refusals.py`. Through
the editor's routes it is `tests/web/test_key_entry_types.py`.

Nothing here touches the filesystem: `refusals` is a pure function over two
documents, and the fixtures build both.
"""

import pytest
from drafted_key_fixtures import ANCHORED_ENTRY, fit_key, reported, scorer_sentence

# What a hand edit leaves where a line number belongs, where a file name does,
# and where the end of a construct does. One table of (field, shape) pairs,
# because the claim is about the pair: a field that is present and of the wrong
# type. `line_end` is the optional one -- `null` and absent are legal for it and
# are asserted at the end, not here.
NOT_A_LINE = {"a string": "4", "null": None, "a list": [4], "a bool": True}
NOT_A_FILE = {"an int": 7, "null": None}
NOT_AN_ID = {"an int": 1, "null": None}
NOT_A_LINE_END = {"a string": "20", "a list": [20], "a bool": True}

WRONG_TYPES = ([("line", shape) for shape in NOT_A_LINE.values()]
               + [("file", shape) for shape in NOT_A_FILE.values()]
               + [("id", shape) for shape in NOT_AN_ID.values()]
               + [("line_end", shape) for shape in NOT_A_LINE_END.values()])
WRONG_TYPE_IDS = ([f"line as {name}" for name in NOT_A_LINE]
                  + [f"file as {name}" for name in NOT_A_FILE]
                  + [f"id as {name}" for name in NOT_AN_ID]
                  + [f"line_end as {name}" for name in NOT_A_LINE_END])

# The two `line_end` values a producer really writes. Absent is the third, and
# is the shape `ANCHORED_ENTRY` already has.
A_REAL_LINE_END = ANCHORED_ENTRY["line"] + 8
MEANS_ONE_LINE = {"null": None, "an int": A_REAL_LINE_END}
ACCEPTED_IDS = list(MEANS_ONE_LINE)
ACCEPTED_SHAPES = list(MEANS_ONE_LINE.values())

# A second fault, so "only the scorer's refusal is reported" is a claim about
# ordering and not about there being nothing else wrong with the key.
WRONG_COUNT = 7

# The one of them used where the test is not about which shape it is: the shape
# that was actually measured.
A_TEXT_LINE = NOT_A_LINE["a string"]


def key_whose_entry_has(field: str, shape: object) -> dict:
    """A fit draft whose one entry carries `shape` in a field that is typed.

    One entry, deliberately: `key_document` sorts the entries it is given, so a
    second one would raise inside the fixture rather than inside the code under
    test.
    """
    return fit_key(({**ANCHORED_ENTRY, field: shape},))


# --- the fault: a field that is present and of the wrong type --------------------

@pytest.mark.parametrize(("field", "shape"), WRONG_TYPES, ids=WRONG_TYPE_IDS)
def test_a_wrong_typed_entry_field_is_reported_rather_than_raised(
        field: str, shape: object) -> None:
    """The measured crash, driven: `_out_of_order` sorts `(file, line, id)` tuples."""
    assert reported(key_whose_entry_has(field, shape)) != []


@pytest.mark.parametrize(("field", "shape"), WRONG_TYPES, ids=WRONG_TYPE_IDS)
def test_the_sentence_reported_is_the_scorers_own(field: str, shape: object) -> None:
    """Why this is an ordering and not a second check here: the scorer already names it.

    Equality, and to a list of one: a copy of these type rules in
    `key_promotion` is exactly what the ordering exists to avoid.
    """
    key = key_whose_entry_has(field, shape)
    assert reported(key) == [scorer_sentence(key)]


@pytest.mark.parametrize(("field", "shape"), WRONG_TYPES, ids=WRONG_TYPE_IDS)
def test_the_scorer_refuses_every_one_of_these_by_name(field: str,
                                                       shape: object) -> None:
    """Non-vacuity: asking the scorer first only answers if the scorer has something to say."""
    assert scorer_sentence(key_whose_entry_has(field, shape))


def test_nothing_after_the_scorers_refusal_is_run() -> None:
    """A draft with a second, ordinary fault still reports one sentence.

    `_miscounted` would report the stale count too, and `_out_of_order` would
    raise before it ever got there -- which is the crash this ordering removes.
    """
    key = {**key_whose_entry_has("line", A_TEXT_LINE), "finding_count": WRONG_COUNT}
    assert reported(key) == [scorer_sentence(key)]


# --- the off positions everything above rests on ---------------------------------

@pytest.mark.parametrize("shape", ACCEPTED_SHAPES, ids=ACCEPTED_IDS)
def test_a_line_end_a_producer_really_writes_is_refused_for_nothing(shape: object) -> None:
    """The optional half: typing `line_end` may not make a legal draft unpromotable.

    Both drafts this project has written carry `line_end: null`, so a check that
    refused it would refuse every real draft while passing every test above.
    """
    assert reported(key_whose_entry_has("line_end", shape)) == []


def test_an_entry_whose_fields_hold_the_types_they_should_is_refused_for_nothing() -> None:
    """Without it, a `refusals` that reported something about every draft would pass above.

    `ANCHORED_ENTRY` carries no `line_end` at all, so this is the absent case too.
    """
    assert "line_end" not in ANCHORED_ENTRY
    assert reported(fit_key((ANCHORED_ENTRY,))) == []
