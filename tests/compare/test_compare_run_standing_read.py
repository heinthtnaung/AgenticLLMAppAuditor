"""The key the comparison's last line reads, in the three states a hand leaves it in.

`_standing` reads a file with a bare `json.loads`. The key it reads was drafted
moments earlier, which is why it looked safe -- but `ensure_key` hands back a
key that already existed as readily as one it just wrote, so the document can be
one a person has since half-saved, replaced with a list, or tightened the
permissions on.

**Where it is called from is the point.** `_summarise` prints it *after* both
arms have audited, published and scored, and after the audited app's source has
already gone to a third party. A traceback there loses the summary of a run that
worked, and takes with it the two lines saying where the artifacts went -- so
the refusal is asserted through `_summarise` too, which needs no model, no clone
and no socket because the arms are two dicts of the two keys it reads.

**The class is the assertion, spelled `type(raised) is ValueError`.** Every
guard in this fault class was defeated by the wrong class rather than by
silence: `AttributeError` from `.get` on a list is not a `ValueError`,
`OSError` is not either, and `json.JSONDecodeError` *is* one -- so `isinstance`
would pass on a decode error let out unwrapped, whose whole message is
"Expecting value: line 1 column 34". `main.EXPECTED_FAILURES` is the seam that
makes the class matter, and it is asserted rather than assumed.

What the summary *says* about a readable key is `test_compare_run_standing.py`.
Nothing here clones or reads a path this project owns: every key is under
`tmp_path`.
"""

import json
from pathlib import Path

import pytest

import compare_run
import main
from drafted_key_fixtures import APP, fit_key
from guarded_read import UNPARSEABLE, WRONG_SHAPE, refusal_from
from keys.grading_keys import TOOL_DRAFTED
from locked_file import locked

# What a text editor leaves behind when a save is interrupted: not json at all.
HALF_SAVED = '{"source": "tool_drafted", "findings": ['

# Readable json that is not a key, with what the refusal must call each one.
# Three shapes because the fault is "not an object" and not "is a list": an edit
# that deleted everything but the entries leaves the first, a truncation either
# of the others.
WRONG_SHAPES = (("[]", "list"), (f'"{APP}"', "str"), ("7", "int"))
SHAPE_IDS = [shape for shape, _name in WRONG_SHAPES]

# What each arm hands `_summarise`: the two keys it reads and nothing else.
LOCAL_ARM = {"artifacts": Path("artifacts") / "agentic_auditor" / APP, "seconds": 1.5}
CLOUD_ARM = {"artifacts": compare_run.cloud_artifacts_dir(
    Path("artifacts") / "agentic_auditor") / APP, "seconds": 2.5}

# The second half of the standing a readable key reads as, for the off position.
UNVERIFIED = "unverified"


def holding(tmp_path: Path, text: str) -> Path:
    """One grading key file holding whatever a hand edit left in it, json or not."""
    path = tmp_path / f"{APP}.ground_truth.json"
    path.write_text(text, encoding="utf-8")
    return path


def a_readable_key(tmp_path: Path) -> Path:
    """A key with nothing wrong with it, so a locked one differs only by its mode."""
    return holding(tmp_path, json.dumps(fit_key(), indent=2, sort_keys=True))


def refused(key: Path) -> Exception:
    """Whatever `_standing` raised, as an object, so its class is what gets asserted."""
    return refusal_from(lambda: compare_run._standing(key), key.name)


def refused_summary(key: Path) -> Exception:
    """The same, through the line of the run `_standing` is really called from."""
    return refusal_from(
        lambda: compare_run._summarise(LOCAL_ARM, CLOUD_ARM, key), "_summarise")


# --- a file that never became json ---------------------------------------------

def test_a_half_saved_key_is_refused_as_a_value_error(tmp_path) -> None:
    """The exact class, because `JSONDecodeError` would satisfy an `isinstance` check."""
    assert type(refused(holding(tmp_path, HALF_SAVED))) is ValueError


def test_the_parse_refusal_names_the_file_and_says_what_went_wrong(tmp_path) -> None:
    """A decode error let out unwrapped names no file, so both halves are asserted."""
    key = holding(tmp_path, HALF_SAVED)
    said = str(refused(key))
    assert str(key) in said and UNPARSEABLE in said


# --- a file nobody can open ----------------------------------------------------

def test_a_key_nobody_can_open_is_refused_as_a_value_error(tmp_path) -> None:
    """`OSError` is not a `ValueError`, and the narrow `except` clause left it out."""
    assert type(refused(locked(a_readable_key(tmp_path)))) is ValueError


def test_the_unopenable_refusal_says_more_than_the_permission_error_would(
        tmp_path) -> None:
    """`PermissionError`'s own message is `[Errno 13] Permission denied: <path>`.

    So a test that only looked for the file name would have passed while the
    exception escaped. The class and this project's own sentence tell them apart.
    """
    key = locked(a_readable_key(tmp_path))
    raised = refused(key)
    assert type(raised) is ValueError
    assert str(key) in str(raised) and UNPARSEABLE in str(raised)


# --- a file that parsed into something else ------------------------------------

@pytest.mark.parametrize("shape,_name", WRONG_SHAPES, ids=SHAPE_IDS)
def test_a_key_that_is_not_an_object_is_refused_rather_than_crashed_on(
        tmp_path, shape: str, _name: str) -> None:
    """`document.get("verified")` on a list is an `AttributeError`, which nothing catches."""
    assert type(refused(holding(tmp_path, shape))) is ValueError


@pytest.mark.parametrize("shape,name", WRONG_SHAPES, ids=SHAPE_IDS)
def test_the_wrong_shape_refusal_names_the_file_and_what_it_held(
        tmp_path, shape: str, name: str) -> None:
    """Both halves of the advice: which file to open, and what it turned out to be."""
    key = holding(tmp_path, shape)
    said = str(refused(key))
    assert str(key) in said
    assert name in said and WRONG_SHAPE in said


def test_the_refusal_is_one_the_command_prints_as_a_reason(tmp_path) -> None:
    """Why `ValueError` and not a clearer class of its own: this list is the seam."""
    assert isinstance(refused(holding(tmp_path, "[]")), main.EXPECTED_FAILURES)


# --- and through the line of the run it is called from -------------------------

@pytest.mark.parametrize("text", [HALF_SAVED] + SHAPE_IDS, ids=["half-saved"] + SHAPE_IDS)
def test_the_summary_refuses_rather_than_ending_a_finished_run_in_a_traceback(
        tmp_path, text: str) -> None:
    """The caller, reached with two dicts: no arm runs, and every fault is one class."""
    assert type(refused_summary(holding(tmp_path, text))) is ValueError


def test_an_unopenable_key_refuses_through_the_summary_too(tmp_path) -> None:
    """The fault that came from the other exception hierarchy, at the same call site."""
    assert type(refused_summary(locked(a_readable_key(tmp_path)))) is ValueError


def test_the_summary_has_already_said_where_both_arms_went(tmp_path, capsys) -> None:
    """What a traceback here costs, stated as the lines a refusal still leaves behind."""
    refused_summary(holding(tmp_path, "[]"))
    printed = capsys.readouterr().out
    assert str(LOCAL_ARM["artifacts"]) in printed
    assert str(CLOUD_ARM["artifacts"]) in printed


def test_a_summary_over_a_readable_key_prints_its_standing(tmp_path, capsys) -> None:
    """The off position: nothing above is satisfied by a summary that refuses everything."""
    compare_run._summarise(LOCAL_ARM, CLOUD_ARM, a_readable_key(tmp_path))
    assert f"({TOOL_DRAFTED}, {UNVERIFIED})" in capsys.readouterr().out
