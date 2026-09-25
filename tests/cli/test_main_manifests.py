"""Guards on a run over manifests it read no version from: named, pointed to, and exit 3."""

import json
import os
from pathlib import Path
from typing import Iterator

import pytest

from cli.main import COULD_NOT_RUN, FOUND_NOTHING, FOUND_NOTHING_BUT_UNREAD, FOUND_SOMETHING
from cli_samples import REPORTS_FOLDER, REPOSITORY_NAME, run_command_line
from report.absences import UNREAD_MANIFEST

NOTHING_FOUND = {"components": (), "advisories": {}}
UNLISTABLE = 0o000
OWNER_ALL = 0o700
NEEDS_PERMISSIONS = pytest.mark.skipif(
    os.geteuid() == 0, reason="root lists anything, so no unreadable directory can be made"
)


def with_unread_manifest(tmp_path: Path) -> Path:
    """Put a `package.json` with no lock file in the repository the command line audits."""
    manifest = tmp_path / REPOSITORY_NAME / "package.json"
    manifest.parent.mkdir(exist_ok=True)
    manifest.write_text("{}", encoding="utf-8")
    return manifest


def with_locked_manifest(tmp_path: Path) -> None:
    """Put a `package.json` beside the lock file Syft reads it from, so nothing is unread."""
    with_unread_manifest(tmp_path)
    (tmp_path / REPOSITORY_NAME / "package-lock.json").write_text("{}", encoding="utf-8")


@pytest.fixture
def locked_out(tmp_path: Path) -> Iterator[Path]:
    """Give the audited repository one directory nobody can list, and unlock it after."""
    closed = tmp_path / REPOSITORY_NAME / "shut"
    closed.mkdir(parents=True)
    closed.chmod(UNLISTABLE)
    yield closed
    closed.chmod(OWNER_ALL)


def test_a_manifest_with_no_lock_file_is_named_and_the_summary_points_to_it(monkeypatch, tmp_path):
    # Found in acceptance testing: "0 findings" at the top over a repository whose
    # manifests had no lock file, and nothing anywhere saying none was read.
    with_unread_manifest(tmp_path)
    given = ["--format", "json"]
    _, out, _ = run_command_line(given, monkeypatch, tmp_path, **NOTHING_FOUND)
    first = json.loads(out)["not_assessed"][0]
    assert first == {"what": "package.json", "because": UNREAD_MANIFEST}
    text = (tmp_path / REPORTS_FOLDER / f"{REPOSITORY_NAME}.txt").read_text(encoding="utf-8")
    assert "Not in these counts: 1 manifest" in text.split("\n\n")[1]


def test_a_run_that_found_nothing_but_could_not_read_a_manifest_exits_three(
    monkeypatch, tmp_path
):
    # Once the accepted gap: it exited 0, and a pipeline went green on
    # dependencies nobody had checked.
    with_unread_manifest(tmp_path)
    code, _, _ = run_command_line([], monkeypatch, tmp_path, **NOTHING_FOUND)
    assert code == FOUND_NOTHING_BUT_UNREAD


def test_a_run_that_found_nothing_and_read_every_manifest_exits_zero(monkeypatch, tmp_path):
    with_locked_manifest(tmp_path)
    code, _, _ = run_command_line([], monkeypatch, tmp_path, **NOTHING_FOUND)
    assert code == FOUND_NOTHING


def test_a_run_with_findings_exits_one_whatever_it_could_not_read(monkeypatch, tmp_path):
    with_unread_manifest(tmp_path)
    code, _, _ = run_command_line([], monkeypatch, tmp_path)
    assert code == FOUND_SOMETHING


@NEEDS_PERMISSIONS
def test_a_directory_that_cannot_be_listed_refuses_the_run_and_says_what_it_was_doing(
    monkeypatch, tmp_path, locked_out
):
    code, out, error = run_command_line([], monkeypatch, tmp_path)
    assert code == COULD_NOT_RUN
    assert out == ""
    assert error == f"audit: cannot list {locked_out} to look for manifests: Permission denied\n"
