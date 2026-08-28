"""The Phase 2 CLI writes all three artifacts, or fails with a message and exit 1.

Syft is stubbed throughout, so this runs offline on a machine that has never
installed it -- the CLI had no test at all before, which is how the defects
below reached an artifact.
"""

import json
import subprocess
import sys
from pathlib import Path

from deps import syft_runner
from parsing.languages import PYTHON
from main import build_parser, main, report_coverage, run
from artifacts.mapping import build_mapping
from dependency_fixtures import corpus_sbom
from artifacts.surface import DATA_SOURCE, PROMPT_TEMPLATE, Surface

ARTIFACT_NAMES = ("sbom.json", "aibom.json", "mapping.json")
APP_NAME = "tiny-app"

# One agent surface importing langchain, so the mapping has something to join.
APP_SOURCE = """from langchain.agents import AgentExecutor

agent = AgentExecutor.from_agent_and_tools(agent=None, tools=[])
"""

STUB_GENERATOR_OUTPUT = {
    "components": [{"type": "library", "name": "langchain", "version": "0.3.25"}],
}
STUB_GENERATOR_VERSION = "1.51.0"


def stub_syft(monkeypatch, scan_result: dict = STUB_GENERATOR_OUTPUT) -> None:
    """Replace both Syft calls, so no subprocess runs and no tool is required."""
    monkeypatch.setattr(syft_runner, "scan", lambda app_dir: scan_result)
    monkeypatch.setattr(syft_runner, "generator_version", lambda: STUB_GENERATOR_VERSION)


def write_app(tmp_path: Path) -> Path:
    """Write a tiny LLM app with one third-party surface and one declared package."""
    repo = tmp_path / APP_NAME
    repo.mkdir()
    (repo / "main.py").write_text(APP_SOURCE, encoding="utf-8")
    (repo / "requirements.txt").write_text("langchain==0.3.25\n", encoding="utf-8")
    return repo


def run_cli(monkeypatch, repo_path: Path, artifacts_dir: Path) -> int:
    """Run the Phase 2 CLI once with the given repo and artifacts directory."""
    argv = ["main.py", str(repo_path), "--artifacts-dir", str(artifacts_dir)]
    monkeypatch.setattr(sys, "argv", argv)
    return main()


def test_writes_all_three_artifacts_and_exits_zero(monkeypatch, tmp_path) -> None:
    """A successful run exits 0 and leaves sbom, aibom and mapping under <app>/."""
    stub_syft(monkeypatch)
    repo = write_app(tmp_path)
    assert run_cli(monkeypatch, repo, tmp_path / "artifacts") == 0
    for name in ARTIFACT_NAMES:
        assert (tmp_path / "artifacts" / APP_NAME / name).is_file(), name


def test_every_written_artifact_parses_and_states_its_schema_version(monkeypatch, tmp_path) -> None:
    """Each file is JSON carrying a schema_version, which is what a reader keys on."""
    stub_syft(monkeypatch)
    run_cli(monkeypatch, write_app(tmp_path), tmp_path / "artifacts")
    for name in ARTIFACT_NAMES:
        text = (tmp_path / "artifacts" / APP_NAME / name).read_text(encoding="utf-8")
        assert json.loads(text)["schema_version"] == 1, name


def test_the_sbom_records_the_stubbed_generator(monkeypatch, tmp_path) -> None:
    """What the generator reported reaches the artifact, so the stub is really used."""
    stub_syft(monkeypatch)
    run_cli(monkeypatch, write_app(tmp_path), tmp_path / "artifacts")
    document = json.loads(
        (tmp_path / "artifacts" / APP_NAME / "sbom.json").read_text(encoding="utf-8")
    )
    assert document["generator_version"] == STUB_GENERATOR_VERSION
    assert [c["name"] for c in document["components"]] == ["langchain"]


def test_run_returns_zero_when_called_directly(monkeypatch, tmp_path) -> None:
    """`run` is the unit that does the work; it reports success with 0, not None."""
    stub_syft(monkeypatch)
    repo = write_app(tmp_path)
    args = build_parser().parse_args([str(repo), "--artifacts-dir", str(tmp_path / "out")])
    assert run(args) == 0


def test_no_subprocess_is_started(monkeypatch, tmp_path) -> None:
    """With Syft stubbed the run is pure Python, so it works with no tool installed."""
    def boom(*args, **kwargs):
        raise AssertionError(f"the auditor started a subprocess: {args}")

    stub_syft(monkeypatch)
    monkeypatch.setattr(subprocess, "run", boom)
    assert run_cli(monkeypatch, write_app(tmp_path), tmp_path / "artifacts") == 0


def test_missing_repo_path_returns_one_with_a_message(monkeypatch, tmp_path, capsys) -> None:
    """A path that does not exist exits 1 with a message, not a traceback."""
    stub_syft(monkeypatch)
    assert run_cli(monkeypatch, tmp_path / "no-such-app", tmp_path / "artifacts") == 1
    assert "does not exist" in capsys.readouterr().err


def test_a_failing_generator_is_reported_not_raised(monkeypatch, tmp_path, capsys) -> None:
    """Syft missing or failing is an expected failure: exit 1 naming what went wrong."""
    def refuse(app_dir):
        raise RuntimeError("syft is not installed")

    stub_syft(monkeypatch)
    monkeypatch.setattr(syft_runner, "scan", refuse)
    assert run_cli(monkeypatch, write_app(tmp_path), tmp_path / "artifacts") == 1
    assert "syft is not installed" in capsys.readouterr().err


def coverage_mapping() -> dict:
    """A mapping with one first-party surface and one undeclared dependency."""
    surfaces = [
        Surface(kind=PROMPT_TEMPLATE, name="system_msg", file="app.py", line=1,
                language=PYTHON, detail="", module=""),
        Surface(kind=DATA_SOURCE, name="yaml.load", file="app.py", line=2,
                language=PYTHON, detail="", module="yaml"),
    ]
    return build_mapping(surfaces, corpus_sbom())


def test_report_coverage_prints_how_much_was_mapped(capsys) -> None:
    """The mapped share is printed, since an artifact on disk cannot show it."""
    report_coverage(coverage_mapping())
    assert "mapped 0 of 2 surfaces (0%)" in capsys.readouterr().err


def test_report_coverage_lists_only_the_non_zero_reasons(capsys) -> None:
    """A reason nobody hit is left out, so the summary shows what actually happened."""
    report_coverage(coverage_mapping())
    error_text = capsys.readouterr().err
    assert "first_party" in error_text
    assert "used_but_undeclared" in error_text
    assert "stdlib" not in error_text


def test_report_coverage_names_each_undeclared_component(capsys) -> None:
    """The supply-chain finding is named on its own line, not just counted."""
    report_coverage(coverage_mapping())
    assert "used but never declared: pyyaml" in capsys.readouterr().err


def test_report_coverage_of_an_empty_mapping_says_n_a(capsys) -> None:
    """No surfaces means no share to report; it must not divide by zero."""
    report_coverage(build_mapping([], corpus_sbom()))
    assert "mapped 0 of 0 surfaces (n/a)" in capsys.readouterr().err
