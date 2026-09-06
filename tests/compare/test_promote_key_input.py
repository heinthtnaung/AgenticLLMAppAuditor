"""The two files the command reads, and what it says when one of them is unusable.

A draft is hand-edited between being written and being promoted, so the pair on
disk is the least trustworthy input this project has: it can be absent, or saved
half-way through an edit. Either way the command owes whoever typed it a
sentence naming the file -- a `JSONDecodeError` traceback out of `promote_key`
would send someone reading the auditor's source instead of their own key.

The command half is asserted through `main`, which is where "a message, not a
traceback" is actually decided: it catches `EXPECTED_FAILURES`, prints one line
and returns an exit code. It reads `key_drafting.DRAFTED_KEYS_DIR`, which
`conftest`'s autouse fixture has already pointed at a temporary folder, so the
success case here also demonstrates that redirection working.
"""

import re
from pathlib import Path

from keys import key_drafting
import promote_key
import pytest
from drafted_key_fixtures import (
    APP,
    DRAFTS_NAME,
    ENTRY,
    corrected_draft,
    fit_key,
    redirect_keys_dir,
)
from keys.grading_keys import GROUND_TRUTH_SUFFIX, MANIFEST_SUFFIX, key_path

# What a text editor leaves behind when a save is interrupted: not JSON.
HALF_SAVED = '{"app": "some-fetched-app", "findings": ['

# The exit codes `main` returns, spelled once.
FAILED, SUCCEEDED = 1, 0


@pytest.fixture
def keys_dir(monkeypatch, tmp_path) -> Path:
    """An empty keys folder under `tmp_path`, with `KEYS_DIR` pointed at it."""
    return redirect_keys_dir(monkeypatch, tmp_path)


@pytest.fixture
def drafts_dir(keys_dir: Path) -> Path:
    """The drafts folder one level down, where a draft waits to be promoted."""
    return keys_dir / DRAFTS_NAME


def run_command(monkeypatch, capsys) -> tuple[int, str]:
    """Run `promote_key.py <app>` and return its exit code and what it said on stderr."""
    monkeypatch.setattr("sys.argv", ["promote_key.py", APP])
    code = promote_key.main()
    return code, capsys.readouterr().err


# --- reading one document ------------------------------------------------------

def test_a_missing_file_is_refused_by_name(tmp_path) -> None:
    """The path is in the message, because the caller's next move is to go and look."""
    missing = tmp_path / f"{APP}{GROUND_TRUTH_SUFFIX}"
    with pytest.raises(FileNotFoundError, match=re.escape(str(missing))):
        promote_key._read(missing)


def test_unparseable_json_is_refused_by_name(tmp_path) -> None:
    """A half-saved key is a syntax problem, and the message says so rather than raising deep."""
    broken = tmp_path / f"{APP}{GROUND_TRUTH_SUFFIX}"
    broken.write_text(HALF_SAVED, encoding="utf-8")
    with pytest.raises(ValueError, match="is not readable json"):
        promote_key._read(broken)


def test_the_json_refusal_names_the_file_too(tmp_path) -> None:
    """Two documents are read, so which one will not parse is the useful half."""
    broken = tmp_path / f"{APP}{MANIFEST_SUFFIX}"
    broken.write_text(HALF_SAVED, encoding="utf-8")
    with pytest.raises(ValueError, match=re.escape(str(broken))):
        promote_key._read(broken)


# --- reading the pair a promotion needs ----------------------------------------

def test_promoting_with_no_draft_at_all_names_the_draft(drafts_dir) -> None:
    """The commonest mistake: the app was never drafted, or was drafted under another name."""
    drafts_dir.mkdir(parents=True)
    with pytest.raises(FileNotFoundError,
                       match=re.escape(str(key_path(APP, GROUND_TRUTH_SUFFIX, drafts_dir)))):
        promote_key.promote(APP, drafts_dir)


def test_promoting_a_key_whose_pin_is_missing_names_the_pin(drafts_dir) -> None:
    """An unpinned key would poison discovery for every app, so it is stopped here."""
    corrected_draft(drafts_dir)
    key_path(APP, MANIFEST_SUFFIX, drafts_dir).unlink()
    with pytest.raises(FileNotFoundError,
                       match=re.escape(str(key_path(APP, MANIFEST_SUFFIX, drafts_dir)))):
        promote_key.promote(APP, drafts_dir)


# --- what the command prints ---------------------------------------------------

def test_a_missing_draft_is_reported_and_exits_one(keys_dir, monkeypatch,
                                                   capsys) -> None:
    """`main` turns the refusal into one line on stderr instead of a traceback."""
    code, said = run_command(monkeypatch, capsys)
    assert code == FAILED
    assert said.startswith("error: ") and APP in said


def test_an_unfit_draft_is_reported_and_exits_one(keys_dir, monkeypatch,
                                                  capsys) -> None:
    """The same for the refusal that has a list in it: printed, not raised."""
    corrected_draft(key_drafting.DRAFTED_KEYS_DIR, key=fit_key((ENTRY,)))
    code, said = run_command(monkeypatch, capsys)
    assert code == FAILED
    assert "code_anchor" in said


def test_a_promotion_from_the_default_drafts_folder_succeeds(keys_dir, monkeypatch,
                                                             capsys) -> None:
    """The command with no path argument reads `DRAFTED_KEYS_DIR`, and the key lands."""
    corrected_draft(key_drafting.DRAFTED_KEYS_DIR)
    code, said = run_command(monkeypatch, capsys)
    assert (code, said) == (SUCCEEDED, "")
    assert key_path(APP, GROUND_TRUTH_SUFFIX, keys_dir).is_file()


def test_the_command_says_the_drafted_source_was_kept(keys_dir, monkeypatch,
                                                      capsys) -> None:
    """Whoever promotes a key is told the qualification survived, since nothing else says so."""
    corrected_draft(key_drafting.DRAFTED_KEYS_DIR)
    monkeypatch.setattr("sys.argv", ["promote_key.py", APP])
    promote_key.main()
    printed = capsys.readouterr().out
    assert "source and verified are unchanged" in printed
