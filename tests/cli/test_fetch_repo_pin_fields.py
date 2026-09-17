"""A pin that IS a json object and whose `upstream_commit` is not a string.

The layer under `test_fetch_repo_pin_read.py`. That file holds the three ways
the *file* goes wrong -- unparseable, not an object, unopenable -- and the guard
written for them stopped at the root: whatever `upstream_commit` held came back
untouched. So `upstream_commit: 12345` parsed, passed the guard, and reached
`check_tree_matches_pin`'s `wanted[:12]` as `TypeError: 'int' object is not
subscriptable` -- which is neither in `main.EXPECTED_FAILURES` nor a `ValueError`
for `web/source_routes._pin_note` to turn into a note, so it was a traceback on
one path and a 500 on the other. A guard that validates the document and not the
member it is read for moves the traceback one frame.

**A non-string is "" and not a refusal**, which is the same answer this reader
already gives a pin that simply names no commit: the caller then reports "pinned
to nothing", and `keys/grading_keys._pinned_commit` has had that exact line for
the same field all along. A test below asks both, because two readers of one
field that disagree is how this came to be worth writing down.

What a reader on the page sees is `tests/web/test_source_pin_member_shapes.py`.

Nothing here clones or runs git: a tree with no `.git` never reaches `read_pin`,
and every file is written into `tmp_path`.
"""

import json
from pathlib import Path

import pytest

import fetch_repo
from fetch_helpers import COMMIT, COMMIT_DATE, NAME, URL, a_pin, a_pinned_tree
from keys import grading_keys

# What a hand edit leaves where a commit belongs. Each is valid json in a valid
# json object, which is exactly why the root guard let it through.
NOT_A_COMMIT = {"an int": 12345, "a list": ["c" * 40], "null": None,
                "an object": {"sha": "c" * 40}}
SHAPE_IDS = list(NOT_A_COMMIT)
SHAPES = list(NOT_A_COMMIT.values())

# What a pin that names no usable commit answers with: the same empty string a
# pin with no `upstream_commit` at all earns.
NAMES_NO_COMMIT = ""

# What the tree check says about a tool-fetched tree, whose history the fetch
# deleted once it had read the commit.
CANNOT_BE_CHECKED = "carries no history"


def a_pin_whose_commit_is(root: Path, shape: object) -> Path:
    """The pin a fetch writes, with the commit replaced by something that is not one."""
    document = {**fetch_repo.manifest(NAME, URL, COMMIT, COMMIT_DATE),
                "upstream_commit": shape}
    return a_pin(root, json.dumps(document))


def answered(call, what: str) -> object:
    """What one call returned, failing with the class of anything that escaped instead.

    The opposite claim to `guarded_read.refusal_from`, and it needs the same
    breadth: every defect in this class was an exception of a class the caller
    was not written for, so the failure message has to name the one that got out.
    """
    try:
        return call()
    except Exception as escaped:  # noqa: BLE001 - the class that escapes is the defect
        raise AssertionError(f"{what} raised {type(escaped).__name__} instead of "
                             f"answering: {escaped}") from escaped


# --- the field itself -----------------------------------------------------------

@pytest.mark.parametrize("shape", SHAPES, ids=SHAPE_IDS)
def test_a_commit_that_is_not_a_string_reads_back_as_no_commit(tmp_path,
                                                               shape: object) -> None:
    """The fix in one line: the member is guarded, not just the document holding it."""
    pin = a_pin_whose_commit_is(tmp_path, shape)
    assert answered(lambda: fetch_repo._pinned_commit(pin), pin.name) == NAMES_NO_COMMIT


@pytest.mark.parametrize("shape", SHAPES, ids=SHAPE_IDS)
def test_the_other_reader_of_this_field_answers_the_same(tmp_path,
                                                         shape: object) -> None:
    """Two modules read `upstream_commit`; one had the right line and one did not.

    Asserted rather than trusted, because a reader that disagrees about what a
    pin says is how a tree comes to be checked against a commit nothing pins.
    """
    pin = a_pin_whose_commit_is(tmp_path, shape)
    assert answered(lambda: grading_keys._pinned_commit(pin), pin.name) == NAMES_NO_COMMIT


def test_a_commit_that_is_a_string_still_comes_back(tmp_path) -> None:
    """The off position: without it, a reader that answered "" to everything would pass."""
    pin = a_pin_whose_commit_is(tmp_path, COMMIT)
    assert fetch_repo._pinned_commit(pin) == COMMIT


# --- and the caller that slices it ----------------------------------------------

@pytest.mark.parametrize("shape", SHAPES, ids=SHAPE_IDS)
def test_the_tree_check_reports_rather_than_raising_on_such_a_pin(tmp_path,
                                                                  shape: object) -> None:
    """Where the `TypeError` actually came out: `wanted[:12]` in the sentence it composes."""
    a_pin_whose_commit_is(tmp_path, shape)
    tree = a_pinned_tree(tmp_path)
    note = answered(lambda: fetch_repo.check_tree_matches_pin(tree), "the tree check")
    assert CANNOT_BE_CHECKED in note


def test_the_note_still_names_the_tree_it_could_not_check(tmp_path) -> None:
    """A note naming neither the tree nor the reason would tell a reader nothing."""
    a_pin_whose_commit_is(tmp_path, NOT_A_COMMIT["an int"])
    assert NAME in fetch_repo.check_tree_matches_pin(a_pinned_tree(tmp_path))


def test_a_pin_that_really_names_a_commit_quotes_it_in_the_note(tmp_path) -> None:
    """The off position for the caller: the twelve characters the slice is there for."""
    a_pin_whose_commit_is(tmp_path, COMMIT)
    assert COMMIT[:12] in fetch_repo.check_tree_matches_pin(a_pinned_tree(tmp_path))
