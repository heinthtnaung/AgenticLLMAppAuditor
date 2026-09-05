"""What the fetch command refuses, and what it prints when it does.

Separate from test_fetch_repo.py, which covers the fetch itself. This file is
about the two things a person meets: the name collision that would quietly
overwrite a graded fixture's artifacts, and the exit codes.
"""

from pathlib import Path

import pytest

import fetch_repo
from fetch_helpers import NAME, URL, download_root, install_fake_git
from grading_keys import GROUND_TRUTH_SUFFIX

GRADED_APP = "a-graded-app"
GRADED_URL = f"https://github.com/someone/{GRADED_APP}"


def plant_key(tmp_path: Path, app: str) -> Path:
    """Write one grading key into a temporary keys directory and return it.

    This project ships no grading key, so the collision guard refuses nothing
    until somebody adds one -- which means the test has to add one. The
    directory is handed to `fetch` and to the guard as an argument, so nothing
    here replaces a module global.
    """
    keys_dir = tmp_path / "grading_keys"
    keys_dir.mkdir()
    (keys_dir / f"{app}{GROUND_TRUTH_SUFFIX}").write_text("{}", encoding="utf-8")
    return keys_dir


def test_fetching_under_a_graded_apps_name_is_refused(tmp_path, monkeypatch) -> None:
    """The download root is not the keys directory, but artifacts are keyed by name alone.

    `main.py` writes to `artifacts/agentic_auditor/<directory name>`, so a tree
    fetched under a graded app's name would overwrite the artifacts
    `evaluate.py` scores against that app's key.
    """
    keys_dir = plant_key(tmp_path, GRADED_APP)
    with pytest.raises(ValueError, match="graded app"):
        fetch_repo.fetch(GRADED_URL, download_root(tmp_path), keys_dir)


def test_the_refusal_says_to_fetch_it_under_another_name(tmp_path, monkeypatch) -> None:
    """The reader can fix this, so the message says how rather than only what."""
    keys_dir = plant_key(tmp_path, GRADED_APP)
    with pytest.raises(ValueError, match="Fetch it under another name"):
        fetch_repo.fetch(GRADED_URL, download_root(tmp_path), keys_dir)


def test_the_same_name_is_allowed_when_no_key_claims_it(tmp_path, monkeypatch) -> None:
    """Guard: the guard is data-driven, so with no key planted it must refuse nothing.

    Without this the test above would pass on a check that refused every name,
    and shipping no keys would mean shipping a fetch command that never runs.
    """
    keys_dir = plant_key(tmp_path, "some-other-app")
    install_fake_git(monkeypatch)
    assert fetch_repo.check_not_a_graded_app(GRADED_APP, keys_dir) is None


# --- The command itself ------------------------------------------------------

def test_the_command_reports_a_refusal_as_an_exit_code_not_a_traceback(
        capsys, monkeypatch) -> None:
    """A bad URL is something the user can fix, so it prints a message and exits 1."""
    monkeypatch.setattr("sys.argv", ["fetch_repo.py", "file:///etc/passwd"])
    assert fetch_repo.main() == 1
    assert "only https:// URLs are fetched" in capsys.readouterr().err


def test_the_command_exits_zero_and_says_where_the_tree_went(
        capsys, monkeypatch, tmp_path) -> None:
    """The happy path returns 0 and names the directory to audit next."""
    install_fake_git(monkeypatch)
    root = download_root(tmp_path)
    monkeypatch.setattr("sys.argv", ["fetch_repo.py", URL, "--into", str(root)])
    assert fetch_repo.main() == 0
    assert NAME in capsys.readouterr().out
