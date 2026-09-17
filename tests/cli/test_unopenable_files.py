"""A grading key and a drafted pair nobody can open, through the two commands that read them.

The same fault as `tests/web/test_unopenable_files.py`, in the two readers that
have no route in front of them: `evaluation/harness._read`, which opens the
hand-written grading key, and `promote_key._read`, which opens the hand-edited
draft and its manifest. Both caught `json.JSONDecodeError` alone. Measured
before the fix:

    harness._read     -> PermissionError, is ValueError: False
    promote_key._read -> PermissionError, is ValueError: False

**The class is only half the claim, and the half a unit test would stop at.**
Each command turns its expected failures into a printed line and an exit code --
`evaluate.EXPECTED_FAILURES` lists `ValueError` and not `PermissionError`, and
`promote_key.EXPECTED_FAILURES` the same -- so a guard that raised the right
class while the command still crashed would pass a test on the exception and
fail the person typing it. The exit code and the sentence on stderr are
asserted here for that reason.

**And promotion moves files.** `promote` ends in two `shutil.move` calls, so a
refusal that half-promoted would be the write-before-validate defect again, in
the one place where the destination is `grading_keys/` and the thing moved is
the answer key a published figure is measured against. Both reads happen before
either move, and that ordering is asserted rather than read off the source: the
keys folder must be empty afterwards and both files still in drafts.

`KEYS_DIR` is redirected under `tmp_path` by `redirect_keys_dir` before any
promotion runs -- the real folder is this project's committed evidence -- and
the evaluation half passes its keys directory in as an argument.
"""

from pathlib import Path

import pytest

import promote_key
from drafted_key_fixtures import (
    APP as DRAFT_APP, DRAFTS_NAME, corrected_draft, redirect_keys_dir)
from evaluate_helpers import run_evaluate, stage_artifacts, stage_keys
from evaluation import harness
from evaluation.document import AGENTIC_AUDITOR
from evaluation_fixtures import APP
from guarded_read import UNPARSEABLE, refusal_from
from keys import key_drafting
from keys.grading_keys import GROUND_TRUTH_SUFFIX, MANIFEST_SUFFIX, key_path
from locked_file import locked

# The exit codes a command returns, spelled once.
FAILED = 1

# A traceback reaches the terminal without this prefix; `main` writes it on
# every refusal it expects.
PRINTED_REASON = "error: "

# The two hand-edited files of a draft, by the suffix that names each. Both are
# read before anything moves, so either one being unopenable must stop the whole
# promotion.
DRAFT_FILES = {"the key": GROUND_TRUTH_SUFFIX, "the manifest": MANIFEST_SUFFIX}


def a_scorable_run(tmp_path: Path) -> tuple[Path, Path]:
    """One app with a grading key and one system's artifacts, ready to be scored."""
    return stage_keys(tmp_path), stage_artifacts(tmp_path)


def locked_key(keys_dir: Path) -> Path:
    """Take every permission off the staged grading key, proving the read really fails."""
    return locked(key_path(APP, GROUND_TRUTH_SUFFIX, keys_dir))


def a_draft_to_promote(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    """A corrected draft under a redirected keys folder: the state promotion starts from."""
    keys_dir = redirect_keys_dir(monkeypatch, tmp_path)
    drafts_dir = keys_dir / DRAFTS_NAME
    corrected_draft(drafts_dir)
    return keys_dir, drafts_dir


def promoted_files(keys_dir: Path) -> list[str]:
    """Every file promotion would have moved up, so "nothing moved" is a list and not a hunch."""
    return sorted(path.name for path in keys_dir.iterdir() if path.is_file())


# --- the grading key, through the evaluation command -------------------------------

def test_a_grading_key_nobody_can_open_is_refused_as_a_value_error(tmp_path) -> None:
    """`PermissionError` is not a `ValueError`, so it went past the command's own catch."""
    keys_dir, artifacts_dir = a_scorable_run(tmp_path)
    locked_key(keys_dir)
    raised = refusal_from(
        lambda: harness.load_app(APP, artifacts_dir / AGENTIC_AUDITOR, keys_dir=keys_dir),
        "load_app")
    assert isinstance(raised, ValueError)
    assert not isinstance(raised, PermissionError)


def test_the_refusal_says_more_than_the_os_error_would(tmp_path) -> None:
    """`PermissionError` names the path itself, so looking for the name proves nothing.

    Its own message is `[Errno 13] Permission denied: <path>`. The class, and
    the project's own sentence, are what tell the escaping exception from the
    refusal.
    """
    keys_dir, artifacts_dir = a_scorable_run(tmp_path)
    path = locked_key(keys_dir)
    raised = refusal_from(
        lambda: harness.load_app(APP, artifacts_dir / AGENTIC_AUDITOR, keys_dir=keys_dir),
        "load_app")
    assert type(raised) is ValueError
    assert UNPARSEABLE in str(raised)
    assert str(path) in str(raised)


def test_an_unopenable_key_exits_one_rather_than_crashing(tmp_path, monkeypatch) -> None:
    """The half a unit test stops short of: the command has to answer, not raise."""
    keys_dir, artifacts_dir = a_scorable_run(tmp_path)
    locked_key(keys_dir)
    assert run_evaluate(monkeypatch, artifacts_dir, keys_dir=keys_dir) == FAILED


def test_the_evaluation_command_prints_one_line_naming_the_key(
        tmp_path, monkeypatch, capsys) -> None:
    """What a reader gets instead of a traceback: the file, and why it could not be read."""
    keys_dir, artifacts_dir = a_scorable_run(tmp_path)
    path = locked_key(keys_dir)
    run_evaluate(monkeypatch, artifacts_dir, keys_dir=keys_dir)
    said = capsys.readouterr().err
    assert said.startswith(PRINTED_REASON)
    assert str(path) in said and UNPARSEABLE in said


def test_a_readable_key_still_scores(tmp_path, monkeypatch) -> None:
    """The off position: nothing above is satisfied by a command that refuses everything."""
    keys_dir, artifacts_dir = a_scorable_run(tmp_path)
    assert run_evaluate(monkeypatch, artifacts_dir, keys_dir=keys_dir) == 0


# --- the draft and its manifest, through the promotion command ----------------------

@pytest.mark.parametrize("suffix", list(DRAFT_FILES.values()), ids=list(DRAFT_FILES))
def test_an_unopenable_draft_file_is_refused_as_a_value_error(monkeypatch, tmp_path,
                                                              suffix: str) -> None:
    """Either file, and the class is what `promote_key.EXPECTED_FAILURES` catches."""
    _keys_dir, drafts_dir = a_draft_to_promote(monkeypatch, tmp_path)
    path = locked(key_path(DRAFT_APP, suffix, drafts_dir))
    raised = refusal_from(lambda: promote_key.promote(DRAFT_APP, drafts_dir), "promote")
    assert type(raised) is ValueError
    assert not isinstance(raised, PermissionError)
    assert str(path) in str(raised)


@pytest.mark.parametrize("suffix", list(DRAFT_FILES.values()), ids=list(DRAFT_FILES))
def test_nothing_is_moved_into_the_keys_folder_when_a_file_cannot_be_opened(
        monkeypatch, tmp_path, suffix: str) -> None:
    """The assertion with teeth: a half-promotion would put an unread key where figures are scored.

    Locking the *manifest* is the ordering case -- the key is read first and
    read fine -- and it is the one a promotion that moved as it went would get
    wrong.
    """
    keys_dir, drafts_dir = a_draft_to_promote(monkeypatch, tmp_path)
    locked(key_path(DRAFT_APP, suffix, drafts_dir))
    refusal_from(lambda: promote_key.promote(DRAFT_APP, drafts_dir), "promote")
    assert promoted_files(keys_dir) == []


@pytest.mark.parametrize("suffix", list(DRAFT_FILES.values()), ids=list(DRAFT_FILES))
def test_both_files_are_left_in_the_drafts_folder(monkeypatch, tmp_path,
                                                  suffix: str) -> None:
    """The other half of "nothing moved": they are still where a person can fix them."""
    _keys_dir, drafts_dir = a_draft_to_promote(monkeypatch, tmp_path)
    locked(key_path(DRAFT_APP, suffix, drafts_dir))
    refusal_from(lambda: promote_key.promote(DRAFT_APP, drafts_dir), "promote")
    assert sorted(path.name for path in drafts_dir.iterdir()) == [
        f"{DRAFT_APP}{GROUND_TRUTH_SUFFIX}", f"{DRAFT_APP}{MANIFEST_SUFFIX}"]


def test_the_promotion_command_prints_one_line_and_exits_one(monkeypatch, tmp_path,
                                                             capsys) -> None:
    """Through `main`, where "a message, not a traceback" is actually decided.

    The command takes no folder argument, so the draft has to be planted where
    it really looks: `key_drafting.DRAFTED_KEYS_DIR`, which `conftest`'s autouse
    fixture has already pointed at a temporary folder of its own.
    """
    redirect_keys_dir(monkeypatch, tmp_path)
    drafts_dir = key_drafting.DRAFTED_KEYS_DIR
    corrected_draft(drafts_dir)
    locked(key_path(DRAFT_APP, GROUND_TRUTH_SUFFIX, drafts_dir))
    monkeypatch.setattr("sys.argv", ["promote_key.py", DRAFT_APP])
    assert promote_key.main() == FAILED
    said = capsys.readouterr().err
    assert said.startswith(PRINTED_REASON) and UNPARSEABLE in said


def test_a_draft_nobody_locked_still_promotes(monkeypatch, tmp_path) -> None:
    """The off position: the staged pair is fit, so "nothing moved" means the lock stopped it."""
    keys_dir, drafts_dir = a_draft_to_promote(monkeypatch, tmp_path)
    promote_key.promote(DRAFT_APP, drafts_dir)
    assert promoted_files(keys_dir) == [
        f"{DRAFT_APP}{GROUND_TRUTH_SUFFIX}", f"{DRAFT_APP}{MANIFEST_SUFFIX}"]
