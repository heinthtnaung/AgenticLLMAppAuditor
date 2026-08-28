"""The Phase 2 CLI writes all five artifacts, or fails with a message and exit 1.

Syft is stubbed throughout, so this runs offline on a machine that has never
installed it.
"""

import subprocess
from pathlib import Path

from cli_helpers import STUB_GENERATOR_VERSION, read_artifact, run_cli, stub_syft
from deps import syft_runner
from deps.package_names import PYPI
from deps.requirements_parser import MANIFEST_NAME as PYPI_MANIFEST
from parsing.languages import PYTHON
from main import (
    AIBOM_NAME,
    CYCLONEDX_NAME,
    MAPPING_NAME,
    SBOM_NAME,
    SURFACES_NAME,
    build_parser,
    dependency_artifacts,
    report_coverage,
    run,
)
from artifacts.mapping import build_mapping
from dependency_fixtures import corpus_sbom
from artifacts.surface import DATA_SOURCE, PROMPT_TEMPLATE, Surface

# Each artifact versions independently, so a shared number would be a
# coincidence rather than a contract. Two of the three went to 2 in the npm
# change: sbom.json when `locked` joined the vocabulary, mapping.json when an
# ambiguous join stopped copying the component's purl and started synthesising
# a version-less one. aibom.json did not move.
EXPECTED_SCHEMA_VERSIONS = {SBOM_NAME: 2, AIBOM_NAME: 1, MAPPING_NAME: 2}

# The artifacts carrying this project's own schema_version. Derived from the
# table above, so a future artifact cannot be listed here and left unchecked.
ARTIFACT_NAMES = tuple(EXPECTED_SCHEMA_VERSIONS)

# Everything a successful run leaves on disk, including the standard-format
# bill, which carries CycloneDX's version rather than one of ours.
ALL_ARTIFACT_NAMES = (SURFACES_NAME, CYCLONEDX_NAME) + ARTIFACT_NAMES
APP_NAME = "tiny-app"

# One agent surface importing langchain, so the mapping has something to join.
APP_SOURCE = """from langchain.agents import AgentExecutor

agent = AgentExecutor.from_agent_and_tools(agent=None, tools=[])
"""

STUB_GENERATOR_OUTPUT = {
    "components": [{"type": "library", "name": "langchain", "version": "0.3.25"}],
}


def write_app(tmp_path: Path) -> Path:
    """Write a tiny LLM app with one third-party surface and one declared package."""
    repo = tmp_path / APP_NAME
    repo.mkdir()
    (repo / "main.py").write_text(APP_SOURCE, encoding="utf-8")
    (repo / PYPI_MANIFEST).write_text("langchain==0.3.25\n", encoding="utf-8")
    return repo


def test_writes_the_sbom_aibom_and_mapping_and_exits_zero(monkeypatch, tmp_path) -> None:
    """A successful run exits 0 and leaves sbom, aibom and mapping under <app>/."""
    stub_syft(monkeypatch, STUB_GENERATOR_OUTPUT)
    repo = write_app(tmp_path)
    assert run_cli(monkeypatch, repo, tmp_path / "artifacts") == 0
    for name in ARTIFACT_NAMES:
        assert (tmp_path / "artifacts" / APP_NAME / name).is_file(), name


def test_writes_five_artifacts_and_says_so(monkeypatch, tmp_path, capsys) -> None:
    """Both bills land beside the other three, and the printed count agrees."""
    stub_syft(monkeypatch, STUB_GENERATOR_OUTPUT)
    assert run_cli(monkeypatch, write_app(tmp_path), tmp_path / "artifacts") == 0
    written = sorted(p.name for p in (tmp_path / "artifacts" / APP_NAME).iterdir())
    assert written == sorted(ALL_ARTIFACT_NAMES)
    assert "wrote 5 artifacts" in capsys.readouterr().out


def test_the_standard_format_bill_is_written_beside_the_project_one(monkeypatch, tmp_path) -> None:
    """sbom.cyclonedx.json is what a reader feeds to other supply-chain tooling."""
    stub_syft(monkeypatch, STUB_GENERATOR_OUTPUT)
    run_cli(monkeypatch, write_app(tmp_path), tmp_path / "artifacts")
    document = read_artifact(tmp_path / "artifacts", APP_NAME, CYCLONEDX_NAME)
    assert [c["name"] for c in document["components"]] == ["langchain"]


def test_dependency_artifacts_returns_both_bills_and_the_mapping(monkeypatch, tmp_path) -> None:
    """The unit that builds them names all three files, so nothing is written by accident."""
    stub_syft(monkeypatch, STUB_GENERATOR_OUTPUT)
    built, _ = dependency_artifacts(write_app(tmp_path), [], PYPI)
    assert sorted(built) == sorted((SBOM_NAME, CYCLONEDX_NAME, MAPPING_NAME))


def test_every_written_artifact_parses_and_states_its_schema_version(monkeypatch, tmp_path) -> None:
    """Each file is JSON carrying its own schema_version, which is what a reader keys on."""
    stub_syft(monkeypatch, STUB_GENERATOR_OUTPUT)
    run_cli(monkeypatch, write_app(tmp_path), tmp_path / "artifacts")
    for name in ARTIFACT_NAMES:
        document = read_artifact(tmp_path / "artifacts", APP_NAME, name)
        assert document["schema_version"] == EXPECTED_SCHEMA_VERSIONS[name], name


def test_the_sbom_records_the_stubbed_generator(monkeypatch, tmp_path) -> None:
    """What the generator reported reaches the artifact, so the stub is really used."""
    stub_syft(monkeypatch, STUB_GENERATOR_OUTPUT)
    run_cli(monkeypatch, write_app(tmp_path), tmp_path / "artifacts")
    document = read_artifact(tmp_path / "artifacts", APP_NAME, SBOM_NAME)
    assert document["generator_version"] == STUB_GENERATOR_VERSION
    assert [c["name"] for c in document["components"]] == ["langchain"]


def test_run_returns_zero_when_called_directly(monkeypatch, tmp_path) -> None:
    """`run` is the unit that does the work; it reports success with 0, not None."""
    stub_syft(monkeypatch, STUB_GENERATOR_OUTPUT)
    repo = write_app(tmp_path)
    args = build_parser().parse_args([str(repo), "--artifacts-dir", str(tmp_path / "out")])
    assert run(args) == 0


def test_no_subprocess_is_started(monkeypatch, tmp_path) -> None:
    """With Syft stubbed the run is pure Python, so it works with no tool installed."""
    def boom(*args, **kwargs) -> None:
        """Fail the test rather than let a real process start."""
        raise AssertionError(f"the auditor started a subprocess: {args}")

    stub_syft(monkeypatch, STUB_GENERATOR_OUTPUT)
    monkeypatch.setattr(subprocess, "run", boom)
    assert run_cli(monkeypatch, write_app(tmp_path), tmp_path / "artifacts") == 0


def test_missing_repo_path_returns_one_with_a_message(monkeypatch, tmp_path, capsys) -> None:
    """A path that does not exist exits 1 with a message, not a traceback."""
    stub_syft(monkeypatch, STUB_GENERATOR_OUTPUT)
    assert run_cli(monkeypatch, tmp_path / "no-such-app", tmp_path / "artifacts") == 1
    assert "does not exist" in capsys.readouterr().err


def test_a_failing_generator_is_reported_not_raised(monkeypatch, tmp_path, capsys) -> None:
    """Syft missing or failing is an expected failure: exit 1 naming what went wrong."""
    def refuse(app_dir: Path) -> dict:
        """Fail the scan the way a missing or broken generator does."""
        raise RuntimeError("syft is not installed")

    stub_syft(monkeypatch, STUB_GENERATOR_OUTPUT)
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
