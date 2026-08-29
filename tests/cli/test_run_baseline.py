"""What `run_baseline.py` writes, where it writes it, and what it refuses.

A baseline writes exactly the two files the scorer opens, into its own system
directory, so `evaluate.py` scores it unmodified and no system can overwrite
another's output. The corpus is staged under `tmp_path`: nothing here reads the
real `corpus/`, and Baseline B's generator is answered from recorded output so
the test needs no Syft.
"""

import json
import sys
from pathlib import Path

import pytest

import evaluate
import run_baseline
from baseline_fixtures import EMPTY_SYFT_DOCUMENT, stub_syft, write_tiny_app
from corpus_paths import (
    DOWNLOAD_HINT,
    GROUND_TRUTH_SUFFIX,
    MANIFEST_SUFFIX,
    discover_corpus_apps,
)
from evaluate_helpers import (
    ARTIFACTS_DIR_NAME,
    CORPUS_DIR_NAME,
    EVIDENCE_DIR_NAME,
    MANIFEST,
    write_json,
)
from evaluation.document import SCORED_SYSTEMS
from evaluation_fixtures import APP, grading_key, key_entry

# A value outside the two baselines, shaped like the directory it would become.
UNKNOWN_SYSTEM = "../etc"


def stage_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, downloaded: bool = True) -> None:
    """Point discovery, the download check and the app lookup at a temporary corpus."""
    evidence, corpus = tmp_path / EVIDENCE_DIR_NAME, tmp_path / CORPUS_DIR_NAME
    (corpus / APP).mkdir(parents=True)
    write_tiny_app(corpus / APP)
    write_json(evidence / f"{APP}{GROUND_TRUTH_SUFFIX}", grading_key([key_entry()]))
    write_json(evidence / f"{APP}{MANIFEST_SUFFIX}", MANIFEST)
    monkeypatch.setattr(run_baseline, "discover_corpus_apps",
                        lambda: discover_corpus_apps(corpus, evidence))
    monkeypatch.setattr(run_baseline, "app_is_present", lambda app: downloaded)
    monkeypatch.setattr(run_baseline, "app_path", lambda app: corpus / app)


def run_cli(monkeypatch: pytest.MonkeyPatch, system: str, artifacts_dir: Path) -> int:
    """Run the entry point through argparse, the way a shell would."""
    monkeypatch.setattr(sys, "argv",
                        ["run_baseline.py", system, "--artifacts-dir", str(artifacts_dir)])
    return run_baseline.main()


def test_it_writes_both_artifacts_under_the_system_and_app_directories(
        tmp_path, monkeypatch) -> None:
    """`artifacts/<system>/<app>/` is what lets three systems be scored side by side."""
    stage_corpus(tmp_path, monkeypatch)
    artifacts_dir = tmp_path / ARTIFACTS_DIR_NAME
    assert run_cli(monkeypatch, run_baseline.STATIC_RULES, artifacts_dir) == 0
    written = artifacts_dir / run_baseline.STATIC_RULES / APP
    assert (written / run_baseline.FINDINGS_NAME).is_file()
    assert (written / run_baseline.SURFACES_NAME).is_file()


def test_the_findings_it_writes_are_the_ones_the_rules_matched(tmp_path, monkeypatch) -> None:
    """The file is the artifact the scorer reads, so its contents are asserted, not its name."""
    stage_corpus(tmp_path, monkeypatch)
    artifacts_dir = tmp_path / ARTIFACTS_DIR_NAME
    run_cli(monkeypatch, run_baseline.STATIC_RULES, artifacts_dir)
    document = json.loads((artifacts_dir / run_baseline.STATIC_RULES / APP /
                           run_baseline.FINDINGS_NAME).read_text(encoding="utf-8"))
    assert document["finding_count"] == 5


def test_the_two_files_it_writes_agree_with_each_other(tmp_path, monkeypatch) -> None:
    """Surfaces derived from the findings, so the pair can never contradict itself."""
    stage_corpus(tmp_path, monkeypatch)
    artifacts_dir = tmp_path / ARTIFACTS_DIR_NAME
    run_cli(monkeypatch, run_baseline.STATIC_RULES, artifacts_dir)
    written = artifacts_dir / run_baseline.STATIC_RULES / APP
    findings = json.loads((written / run_baseline.FINDINGS_NAME).read_text(encoding="utf-8"))
    surfaces = json.loads((written / run_baseline.SURFACES_NAME).read_text(encoding="utf-8"))
    assert ({s["id"] for s in surfaces["surfaces"]}
            == {f["surface_id"] for f in findings["findings"]})


def test_the_sbom_baseline_writes_an_empty_surfaces_file(tmp_path, monkeypatch) -> None:
    """It has no surface model, and the file must exist anyway: the scorer opens it."""
    stage_corpus(tmp_path, monkeypatch)
    stub_syft(monkeypatch, EMPTY_SYFT_DOCUMENT)
    artifacts_dir = tmp_path / ARTIFACTS_DIR_NAME
    assert run_cli(monkeypatch, run_baseline.SBOM_ONLY, artifacts_dir) == 0
    surfaces = json.loads((artifacts_dir / run_baseline.SBOM_ONLY / APP /
                           run_baseline.SURFACES_NAME).read_text(encoding="utf-8"))
    assert surfaces["surfaces"] == []


def test_running_one_baseline_leaves_the_others_output_alone(tmp_path, monkeypatch) -> None:
    """Two systems, two directories: the reason the system segment exists at all."""
    stage_corpus(tmp_path, monkeypatch)
    stub_syft(monkeypatch, EMPTY_SYFT_DOCUMENT)
    artifacts_dir = tmp_path / ARTIFACTS_DIR_NAME
    run_cli(monkeypatch, run_baseline.STATIC_RULES, artifacts_dir)
    run_cli(monkeypatch, run_baseline.SBOM_ONLY, artifacts_dir)
    for system in run_baseline.BASELINES:
        assert (artifacts_dir / system / APP / run_baseline.FINDINGS_NAME).is_file()


def test_a_system_outside_the_two_baselines_is_rejected(tmp_path, monkeypatch) -> None:
    """The value becomes a directory name, so argparse rejects it before a path is built."""
    with pytest.raises(SystemExit) as raised:
        run_cli(monkeypatch, UNKNOWN_SYSTEM, tmp_path / ARTIFACTS_DIR_NAME)
    assert raised.value.code == 2


def test_the_rejected_system_is_never_created_as_a_directory(tmp_path, monkeypatch) -> None:
    """An unvalidated string would land in the filesystem, so nothing may be written first."""
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, UNKNOWN_SYSTEM, tmp_path / ARTIFACTS_DIR_NAME)
    assert not (tmp_path / ARTIFACTS_DIR_NAME).exists()


def test_a_fixture_that_was_never_downloaded_exits_one(tmp_path, monkeypatch) -> None:
    """No source on disk is a refusal, not an app run over nothing and reported as clean."""
    stage_corpus(tmp_path, monkeypatch, downloaded=False)
    assert run_cli(monkeypatch, run_baseline.STATIC_RULES, tmp_path / ARTIFACTS_DIR_NAME) == 1


def test_the_refusal_names_the_app_and_says_where_to_get_it(
        tmp_path, monkeypatch, capsys) -> None:
    """It carries the one download hint `corpus_paths` owns, rather than a traceback."""
    stage_corpus(tmp_path, monkeypatch, downloaded=False)
    run_cli(monkeypatch, run_baseline.STATIC_RULES, tmp_path / ARTIFACTS_DIR_NAME)
    error = capsys.readouterr().err
    assert APP in error and DOWNLOAD_HINT in error


def test_nothing_is_written_when_a_fixture_is_missing(tmp_path, monkeypatch) -> None:
    """A partial run would be scored as a complete one, so it must write no artifact at all."""
    stage_corpus(tmp_path, monkeypatch, downloaded=False)
    run_cli(monkeypatch, run_baseline.STATIC_RULES, tmp_path / ARTIFACTS_DIR_NAME)
    assert not (tmp_path / ARTIFACTS_DIR_NAME).exists()


@pytest.mark.parametrize("system", run_baseline.BASELINES)
def test_every_baseline_is_a_system_the_scorer_knows(system: str) -> None:
    """A baseline the harness cannot name could be run but never scored."""
    assert system in SCORED_SYSTEMS


@pytest.mark.parametrize("system", run_baseline.BASELINES)
def test_every_baseline_is_accepted_by_the_parser(system: str) -> None:
    """The vocabulary is `BASELINES` itself, so adding one needs no edit here."""
    assert run_baseline.build_parser().parse_args([system]).system == system


def test_the_default_artifacts_directory_is_the_one_the_scorer_reads() -> None:
    """`run_baseline` writes `<dir>/<system>/<app>/`, which is where `evaluate` looks."""
    assert run_baseline.DEFAULT_ARTIFACTS_DIR == evaluate.DEFAULT_ARTIFACTS_DIR
