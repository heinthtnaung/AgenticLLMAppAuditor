"""A key entry whose fields are all present and whose `line` or `id` is not text.

**Presence is not type, and this file is that distinction.**
`tests/evaluation/test_key_entry_check.py` holds the first half: every field an
entry needs is required, and an entry carrying only those fields is accepted. It
stopped there -- at whether the fields were *there* -- so `"line": "4"`, which
is one quote-pair away in a file a human retypes, passed the check and crashed
two readers further on:

    grading.line_window    -> TypeError: can only concatenate str (not "int") to str
    key_promotion._out_of_order -> TypeError: '<' not supported between 'int' and 'str'

The first is on the **scoring** path, reached from `src/evaluate.py` through
`grading.matches_key`; the second is on the promotion path. One typed check at
the edge answers both, which is why `TYPED_ENTRY_FIELDS` lives in `harness.py`
beside the presence check rather than in either reader.

**`bool` is excluded on purpose and the reason is not tidiness.** `True` is an
`int` in Python, so `"line": true` crashes nothing at all: `line_window` answers
`(1, 4)` and the entry quietly matches any finding in the first four lines of
the file. A crash is caught by the next person to read the traceback; a key that
scores against the wrong lines is not.

**`id` is the third required field here and the one no hand edit is needed
for.** A model reply labelling an entry `1` reaches the drafter, and the
`(file, line, id)` sort raised out of a `--draft-key` run whose artifacts were
already on disk -- `tests/compare/test_drafted_key_ids.py` is that path, and it
is why the check has to exist at both ends.

`line_end` is the fourth field of this family and is checked by a second map,
because it is optional where these three are required:
`test_key_entry_line_end.py` is its own file for that reason, and because its
boolean shape fails in a different and worse way.

Pure dicts throughout -- `check_key` needs no filesystem. The same key reaching
the scorer from disk is `tests/cli/test_evaluate_refusals.py`; through
promotion, `tests/compare/test_key_promotion_entry_types.py`; through the
editor's routes, `tests/web/test_key_entry_types.py`.
"""

from pathlib import Path

import pytest

from evaluation.grading import LINE_TOLERANCE, line_window
from evaluation.harness import ENTRY_FIELDS, TYPED_ENTRY_FIELDS, check_key
from evaluation_fixtures import grading_key, key_entry
from guarded_read import refusal_from

# Stands in for the path the key was read from; nothing here opens it.
KEY_FILE = Path("grading_keys/an-app.ground_truth.json")

# What a hand edit leaves where a line number belongs. `"4"` is the one that was
# measured; the rest are the other shapes an editor's find-and-replace leaves.
NOT_A_LINE = {"a string": "4", "null": None, "a list": [4], "a bool": True}
LINE_IDS = list(NOT_A_LINE)
LINE_SHAPES = list(NOT_A_LINE.values())

# The same for the field beside it, which is compared and sorted on as a string.
NOT_A_FILE = {"an int": 7, "null": None, "a list": ["agent.py"]}
FILE_IDS = list(NOT_A_FILE)
FILE_SHAPES = list(NOT_A_FILE.values())

# And the label the same sort ends on. This one needs no hand edit at all: a
# model reply labelling an entry `1` reaches the drafter, which is what put it
# in the map after it was argued out of it.
NOT_AN_ID = {"an int": 1, "null": None, "a list": ["K-02"]}
ID_IDS = list(NOT_AN_ID)
ID_SHAPES = list(NOT_AN_ID.values())

# An ordinary entry's two typed values, so the refusals above are not "refuse
# everything".
A_REAL_LINE = 12
A_REAL_FILE = "app/agent.py"
A_REAL_ID = "TINY-07"

# What `line_window` answers for `"line": true`: the first line of the file,
# widened by the tolerance. No exception anywhere, which is the point.
FIRST_LINE = 1


def refuse(entry: dict) -> str:
    """Check a key holding this one entry and return the sentence it is refused with."""
    raised = refusal_from(lambda: check_key(grading_key([entry]), KEY_FILE), "check_key")
    assert isinstance(raised, ValueError), (
        f"check_key raised {type(raised).__name__} instead of refusing: {raised}")
    return str(raised)


# --- line: the field both readers do arithmetic on ------------------------------

@pytest.mark.parametrize("shape", LINE_SHAPES, ids=LINE_IDS)
def test_a_line_that_is_not_a_number_is_refused(shape: object) -> None:
    """The fault itself: the field is present, and nothing downstream can add to it."""
    assert "line" in refuse(key_entry(line=shape))


@pytest.mark.parametrize("shape", LINE_SHAPES, ids=LINE_IDS)
def test_the_refusal_names_the_entry_and_what_it_found(shape: object) -> None:
    """A key with twenty entries is unscannable by eye, so the message points at one."""
    said = refuse(key_entry(line=shape))
    assert "findings[0]" in said
    assert type(shape).__name__ in said


def test_a_real_line_number_is_accepted() -> None:
    """The off position: without it, a check that refused every line would pass above."""
    key = grading_key([key_entry(line=A_REAL_LINE)])
    assert check_key(key, KEY_FILE) is key


# --- file: the field both readers compare and sort on ---------------------------

@pytest.mark.parametrize("shape", FILE_SHAPES, ids=FILE_IDS)
def test_a_file_that_is_not_text_is_refused(shape: object) -> None:
    """`(file, line, id)` is sorted as a tuple, so a non-string here is a `TypeError` too."""
    assert "file" in refuse(key_entry(file=shape))


def test_a_real_file_name_is_accepted() -> None:
    """The off position for the other field, for the same reason."""
    key = grading_key([key_entry(file=A_REAL_FILE)])
    assert check_key(key, KEY_FILE) is key


# --- id: the third element of the same sort -------------------------------------

@pytest.mark.parametrize("shape", ID_SHAPES, ids=ID_IDS)
def test_an_id_that_is_not_text_is_refused(shape: object) -> None:
    """Three places sort on it: `matched_key_ids`, `misses`, and `(file, line, id)`."""
    assert "id" in refuse(key_entry(id=shape))


def test_a_real_id_is_accepted() -> None:
    """The off position for the third field, for the same reason as the other two."""
    key = grading_key([key_entry(id=A_REAL_ID)])
    assert check_key(key, KEY_FILE) is key


# --- why the check is here and not in the readers -------------------------------

def test_the_scorers_own_window_cannot_take_a_line_that_is_text() -> None:
    """Non-vacuity for the whole file: the crash the guard replaces is real.

    `line_window` is what `grading.matches_key` calls for every produced
    finding, so this is the scoring path and not only promotion's.
    """
    raised = refusal_from(lambda: line_window({"line": NOT_A_LINE["a string"]}),
                          "line_window")
    assert isinstance(raised, TypeError), raised


def test_a_true_line_crashes_nothing_and_windows_the_top_of_the_file() -> None:
    """Why `bool` is excluded rather than accepted as the `int` it is.

    Every other shape in the table raises somewhere. This one does not: it
    scores, against whatever the detector found in the first four lines. That is
    the outcome a type check catches and a traceback never would.
    """
    assert line_window({"line": True}) == (FIRST_LINE, FIRST_LINE + LINE_TOLERANCE)


# --- the map itself -------------------------------------------------------------

def test_every_typed_field_is_also_a_required_one() -> None:
    """`_check_entry` subscripts these after the presence check, so an optional one would raise.

    Adding `line_end` -- genuinely optional -- to this map would make
    `entry["line_end"]` a `KeyError` on every key that omits it. It is typed
    all the same, by `NULLABLE_TYPED_ENTRY_FIELDS` and only when it is not
    None; `test_key_entry_line_end.py` is that field's whole story.
    """
    assert set(TYPED_ENTRY_FIELDS) <= set(ENTRY_FIELDS)


def test_the_typed_map_is_the_three_fields_the_scorer_orders_on() -> None:
    """Named as a whole: a fourth field typed here would be a check stricter than the schema.

    `owasp_id` is the one left out, and for a reason that survives: it is only
    ever *compared*, so a wrong-typed one is a key that matches nothing rather
    than a key that crashes.

    **`id` is in, and how it came to be left out is the instructive part.** The
    first version of this test argued that its crash "needs two entries of mixed
    type where `line` needs one", so typing it would be stricter than the
    schema. Both halves were wrong. `docs/SCHEMAS.md` calls `id` a string in the
    required-entry-fields list, three paragraphs above the sentence that claimed
    the opposite -- the argument contradicted the schema it appealed to. And
    "needs a hand edit" was measured false: a model reply naming one surface
    twice with ids `1` and `"K-02"` is enough, and that reply ended a finished
    `--draft-key` run in a traceback. `tests/compare/test_drafted_key_ids.py`
    drives it.
    """
    assert TYPED_ENTRY_FIELDS == {"file": str, "line": int, "id": str}
