"""The CLI writes a valid surfaces.json artifact, including the empty result."""

import json
import subprocess

import pytest

from cli_helpers import run_cli
from conftest import CORPUS_DIR, require_corpus
from main import SURFACES_NAME
from artifacts.surface import SCHEMA_VERSION, SURFACE_KINDS
from artifacts.skipped_file import UNPARSEABLE_SYNTAX
from unreadable_fixtures import (
    BROKEN_PYTHON_FILE,
    BROKEN_TYPESCRIPT_FILE,
    EXPECTED_SKIPS,
    GOOD_FILE,
    GOOD_SOURCE,
    GOOD_SURFACE_NAME,
    write_unreadable_repo,
)

APP = "vuln-app-1-support-agent"

# The synthetic apps: one whose files cannot all be read, one that reads cleanly.
MIXED_APP = "mixed-app"
CLEAN_APP = "clean-app"


def test_writes_surfaces_json_for_a_demo_app(monkeypatch, tmp_path) -> None:
    """Running the CLI on demo app 1 writes <app>/surfaces.json and exits 0."""
    require_corpus("vuln-app-1-support-agent")
    exit_code = run_cli(monkeypatch, CORPUS_DIR / APP, tmp_path)
    assert exit_code == 0
    assert (tmp_path / APP / SURFACES_NAME).is_file()


def test_written_artifact_matches_the_schema(monkeypatch, tmp_path) -> None:
    """The artifact parses and reports the schema version and the real surface count."""
    require_corpus("vuln-app-1-support-agent")
    run_cli(monkeypatch, CORPUS_DIR / APP, tmp_path)
    document = json.loads((tmp_path / APP / SURFACES_NAME).read_text(encoding="utf-8"))
    assert document["schema_version"] == SCHEMA_VERSION
    assert document["surface_count"] == len(document["surfaces"])
    assert document["surfaces"]


def test_written_surfaces_carry_known_kinds(monkeypatch, tmp_path) -> None:
    """Every record in the artifact uses one of the four declared surface kinds."""
    require_corpus("vuln-app-1-support-agent")
    run_cli(monkeypatch, CORPUS_DIR / APP, tmp_path)
    document = json.loads((tmp_path / APP / SURFACES_NAME).read_text(encoding="utf-8"))
    assert {record["kind"] for record in document["surfaces"]} <= set(SURFACE_KINDS)


def test_repo_without_surfaces_succeeds_and_writes_empty_artifact(monkeypatch, tmp_path) -> None:
    """A repo with no LLM surfaces is a valid result: exit 0 and an empty artifact."""
    repo = tmp_path / "plain-app"
    repo.mkdir()
    (repo / "helper.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    artifacts = tmp_path / "artifacts"
    assert run_cli(monkeypatch, repo, artifacts) == 0
    document = json.loads((artifacts / "plain-app" / SURFACES_NAME).read_text(encoding="utf-8"))
    assert document["surface_count"] == 0
    assert document["surfaces"] == []


def test_missing_repo_path_fails_loudly(monkeypatch, tmp_path, capsys) -> None:
    """A path that does not exist exits non-zero with a message, not a traceback."""
    assert run_cli(monkeypatch, tmp_path / "does-not-exist", tmp_path / "artifacts") == 1
    assert "does not exist" in capsys.readouterr().err


def forbid_subprocesses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any attempt to start a process fail the test."""
    def boom(*args, **kwargs) -> None:
        """Fail the test rather than let a real process start."""
        raise AssertionError(f"the auditor started a subprocess: {args}")

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)


def run_on_mixed_repo(monkeypatch, tmp_path) -> tuple[int, dict]:
    """Audit a repo whose files cannot all be read; return the exit code and the artifact."""
    repo = tmp_path / MIXED_APP
    repo.mkdir()
    write_unreadable_repo(repo)
    exit_code = run_cli(monkeypatch, repo, tmp_path / "artifacts")
    artifact = tmp_path / "artifacts" / MIXED_APP / SURFACES_NAME
    return exit_code, json.loads(artifact.read_text(encoding="utf-8"))


def test_repo_with_unreadable_files_still_succeeds(monkeypatch, tmp_path) -> None:
    """Files the parsers could not read are a normal outcome, not a failed run."""
    exit_code, document = run_on_mixed_repo(monkeypatch, tmp_path)
    assert exit_code == 0
    assert document["schema_version"] == SCHEMA_VERSION


def test_readable_file_keeps_its_surface_in_the_artifact(monkeypatch, tmp_path) -> None:
    """The good file's surface reaches the artifact despite three unreadable neighbours."""
    _, document = run_on_mixed_repo(monkeypatch, tmp_path)
    found = [(r["file"], r["name"]) for r in document["surfaces"]]
    assert found == [(GOOD_FILE, GOOD_SURFACE_NAME)]


def test_artifact_records_every_skipped_file(monkeypatch, tmp_path) -> None:
    """Phase 4 grades recall off this artifact, so each skip is written into it."""
    _, document = run_on_mixed_repo(monkeypatch, tmp_path)
    recorded = {(r["file"], r["reason"], r["line"]) for r in document["skipped_files"]}
    assert recorded == EXPECTED_SKIPS


def test_skipped_file_count_matches_the_recorded_list(monkeypatch, tmp_path) -> None:
    """The count is derived from the list, so a reader can trust either one."""
    _, document = run_on_mixed_repo(monkeypatch, tmp_path)
    assert document["skipped_file_count"] == len(document["skipped_files"]) == len(EXPECTED_SKIPS)


def test_skipped_files_are_also_warned_about_on_stderr(monkeypatch, tmp_path, capsys) -> None:
    """The user is told what was skipped while running, not only in the artifact."""
    run_on_mixed_repo(monkeypatch, tmp_path)
    errors = capsys.readouterr().err
    assert f"warning: skipped {BROKEN_PYTHON_FILE}: {UNPARSEABLE_SYNTAX} (line 1)" in errors
    assert f"warning: skipped {BROKEN_TYPESCRIPT_FILE}: {UNPARSEABLE_SYNTAX}\n" in errors


def test_readable_repo_records_no_skips(monkeypatch, tmp_path) -> None:
    """A clean scan says so explicitly, so a partial scan cannot pass for a complete one."""
    repo = tmp_path / CLEAN_APP
    repo.mkdir()
    (repo / GOOD_FILE).write_text(GOOD_SOURCE, encoding="utf-8")
    assert run_cli(monkeypatch, repo, tmp_path / "artifacts") == 0
    artifact = tmp_path / "artifacts" / CLEAN_APP / SURFACES_NAME
    document = json.loads(artifact.read_text(encoding="utf-8"))
    assert document["skipped_file_count"] == 0
    assert document["skipped_files"] == []
