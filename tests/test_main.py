"""The CLI writes a valid surfaces.json artifact, including the empty result."""

import json
import subprocess
import sys

import main as main_module
from conftest import CORPUS_DIR, require_corpus
from main import OUTPUT_NAME, main
from surface import SCHEMA_VERSION, SURFACE_KINDS

APP = "vuln-app-1-support-agent"


def run_cli(monkeypatch, repo_path, artifacts_dir) -> int:
    """Run the CLI once with the given repo and artifacts directory."""
    argv = ["main.py", str(repo_path), "--artifacts-dir", str(artifacts_dir)]
    monkeypatch.setattr(sys, "argv", argv)
    return main()


def test_writes_surfaces_json_for_a_demo_app(monkeypatch, tmp_path) -> None:
    """Running the CLI on demo app 1 writes <app>/surfaces.json and exits 0."""
    require_corpus("vuln-app-1-support-agent")
    exit_code = run_cli(monkeypatch, CORPUS_DIR / APP, tmp_path)
    assert exit_code == 0
    assert (tmp_path / APP / OUTPUT_NAME).is_file()


def test_written_artifact_matches_the_schema(monkeypatch, tmp_path) -> None:
    """The artifact parses and reports the schema version and the real surface count."""
    require_corpus("vuln-app-1-support-agent")
    run_cli(monkeypatch, CORPUS_DIR / APP, tmp_path)
    document = json.loads((tmp_path / APP / OUTPUT_NAME).read_text(encoding="utf-8"))
    assert document["schema_version"] == SCHEMA_VERSION
    assert document["surface_count"] == len(document["surfaces"])
    assert document["surfaces"]


def test_written_surfaces_carry_known_kinds(monkeypatch, tmp_path) -> None:
    """Every record in the artifact uses one of the four declared surface kinds."""
    require_corpus("vuln-app-1-support-agent")
    run_cli(monkeypatch, CORPUS_DIR / APP, tmp_path)
    document = json.loads((tmp_path / APP / OUTPUT_NAME).read_text(encoding="utf-8"))
    assert {record["kind"] for record in document["surfaces"]} <= set(SURFACE_KINDS)


def test_repo_without_surfaces_succeeds_and_writes_empty_artifact(monkeypatch, tmp_path) -> None:
    """A repo with no LLM surfaces is a valid result: exit 0 and an empty artifact."""
    repo = tmp_path / "plain-app"
    repo.mkdir()
    (repo / "helper.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    artifacts = tmp_path / "artifacts"
    assert run_cli(monkeypatch, repo, artifacts) == 0
    document = json.loads((artifacts / "plain-app" / OUTPUT_NAME).read_text(encoding="utf-8"))
    assert document["surface_count"] == 0
    assert document["surfaces"] == []


def test_missing_repo_path_fails_loudly(monkeypatch, tmp_path, capsys) -> None:
    """A path that does not exist exits non-zero with a message, not a traceback."""
    assert run_cli(monkeypatch, tmp_path / "does-not-exist", tmp_path / "artifacts") == 1
    assert "does not exist" in capsys.readouterr().err


def forbid_subprocesses(monkeypatch) -> None:
    """Make any attempt to start a process fail the test."""
    def boom(*args, **kwargs):
        raise AssertionError(f"the auditor started a subprocess: {args}")

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)