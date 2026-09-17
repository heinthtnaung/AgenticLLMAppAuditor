"""Reading the pin: three ways a hand-edited file goes wrong, one refusal for all of them.

`_pin_for` falls back to `grading_keys/<app>.manifest.json`, and that file is
written by a person -- `key_promotion.GRADED_PIN_FIELDS` asks them to type the
framework and language into it. So a half-saved pin, a pin holding a list, and a
pin nobody can open are ordinary states of the file, not hostile input, and
`_pinned_commit` is the guarded read that turns all three into one refusal.

**Every one must be `ValueError`, and the class is the assertion with teeth.**
`json.JSONDecodeError` *is* a `ValueError`; `AttributeError` -- what `.get` on a
list raises -- is not, and neither is `OSError`. A caller catching `ValueError`
therefore caught the unparseable file and crashed on the other two, which is how
this fault survived three earlier fixes of the same class. Both callers are
real: `main.EXPECTED_FAILURES` turns `ValueError` into a printed reason, and
`web/source_routes._pin_note` into the `unchecked` sentence the page shows.

What the tree check does with those refusals is `test_fetch_repo_pin_check.py`;
the producer half -- what a fetch *writes* -- is `test_fetch_repo_manifest.py`.
The staging and the corrupt shapes are `fetch_helpers.py`, so the two files
cannot drift about what a broken pin is.

Nothing here clones, and nothing reads or writes a path this project owns:
every pin goes into `tmp_path`.
"""

from pathlib import Path

import pytest

import fetch_repo
from fetch_helpers import (
    COMMIT, CORRUPT_IDS, CORRUPT_SHAPES, HALF_SAVED, NAME, a_fetched_pin, a_pin)
from guarded_read import refusal_from
from keys.grading_keys import MANIFEST_SUFFIX
from locked_file import locked

# A pin that is a json object and names no commit. Not a refusal: the caller
# reports "pinned to nothing", and that is a different fact from a broken file.
NO_COMMIT = ""

# A second commit, so "the commit came from the file" is a comparison rather
# than a coincidence.
ANOTHER_COMMIT = "b" * 40


def refused(pin: Path) -> Exception:
    """Whatever `_pinned_commit` raised for this pin, as an object, so its class can be asserted.

    The catching is `guarded_read.refusal_from`, shared with the other trees:
    every guard in this fault class was defeated by the wrong *class*, not by
    silence, so `pytest.raises(ValueError)` would report the escaping
    `AttributeError` or `PermissionError` as an error in the test rather than as
    the wrong answer it is.
    """
    return refusal_from(lambda: fetch_repo._pinned_commit(pin), pin.name)


# --- the off position ---------------------------------------------------------

def test_an_ordinary_pin_answers_with_the_commit_it_names(tmp_path) -> None:
    """Nothing below is a refusal of everything: a good pin is read and returned."""
    assert fetch_repo._pinned_commit(a_fetched_pin(tmp_path)) == COMMIT


def test_the_commit_comes_from_the_file_and_is_not_assumed(tmp_path) -> None:
    """Non-vacuity for the test above: a second commit must read back as itself."""
    assert fetch_repo._pinned_commit(a_fetched_pin(tmp_path, ANOTHER_COMMIT)) == ANOTHER_COMMIT


def test_an_object_that_names_no_commit_is_not_a_refusal(tmp_path) -> None:
    """"Pins nothing" is a shape this read answers, not one it raises on.

    The guard is about documents that cannot name a commit at all. A json object
    that simply has no `upstream_commit` can, and says none -- which the caller
    renders as a pin of "".
    """
    assert fetch_repo._pinned_commit(a_pin(tmp_path, "{}")) == NO_COMMIT


# --- and the three faults --------------------------------------------------------

@pytest.mark.parametrize("text,message", CORRUPT_SHAPES, ids=CORRUPT_IDS)
def test_a_hand_edited_pin_is_refused_as_a_value_error(tmp_path, text: str,
                                                       message: str) -> None:
    """One class for every fault, so one `except ValueError` covers the file."""
    with pytest.raises(ValueError, match=message):
        fetch_repo._pinned_commit(a_pin(tmp_path, text))


@pytest.mark.parametrize("text,_message", CORRUPT_SHAPES, ids=CORRUPT_IDS)
def test_the_refusal_names_the_file_a_reader_has_to_fix(tmp_path, text: str,
                                                        _message: str) -> None:
    """Two pins can be in play for one tree, so a refusal that names neither sends nobody anywhere."""
    assert f"{NAME}{MANIFEST_SUFFIX}" in str(refused(a_pin(tmp_path, text)))


def test_a_pin_holding_a_list_raises_value_error_and_not_attribute_error(tmp_path) -> None:
    """The first escape: `.get` on a list is an `AttributeError`, which is not a `ValueError`.

    Asserted as two facts rather than one `pytest.raises`, because the wrong
    class is the whole defect: a caller that catches `ValueError` caught the
    unparseable pin and crashed on this one.
    """
    raised = refused(a_pin(tmp_path, "[]"))
    assert isinstance(raised, ValueError)
    assert not isinstance(raised, AttributeError)


def test_a_pin_nobody_can_open_raises_value_error_and_not_permission_error(tmp_path) -> None:
    """The second escape, by the other exception hierarchy, found while testing the first.

    `OSError` is not a `ValueError` either, so a pin whose permissions were
    tightened went past `main.EXPECTED_FAILURES` as a traceback and past
    `_pin_note` as a 500 -- while the file beside it that merely would not parse
    was reported properly. One `except` clause apart.
    """
    raised = refused(locked(a_fetched_pin(tmp_path)))
    assert isinstance(raised, ValueError)
    assert not isinstance(raised, PermissionError)


def test_an_unopenable_pin_says_more_than_the_os_error_would(tmp_path) -> None:
    """`PermissionError` names the path itself, so looking for the file name proves nothing.

    Its own message is `[Errno 13] Permission denied: <path>`, which satisfies a
    test that only checks the name is mentioned -- measured, by narrowing the
    `except` clause and watching this assertion still pass. The class is what
    tells them apart.
    """
    raised = refused(locked(a_fetched_pin(tmp_path)))
    assert type(raised) is ValueError
    assert f"{NAME}{MANIFEST_SUFFIX}" in str(raised)


def test_an_unreadable_pin_says_more_than_the_json_parser_would(tmp_path) -> None:
    """`JSONDecodeError` is a `ValueError` too, so the class alone proves nothing here.

    A decode error let out unwrapped would satisfy every `ValueError` check in
    this file while telling a reader only "Expecting value: line 1 column 21".
    The exact class and the file name are what tell the two apart.
    """
    raised = refused(a_pin(tmp_path, HALF_SAVED))
    assert type(raised) is ValueError
    assert f"{NAME}{MANIFEST_SUFFIX}" in str(raised)
