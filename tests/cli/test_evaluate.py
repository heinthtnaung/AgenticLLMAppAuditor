"""Where the evaluation entry point writes, and how two systems stay apart.

The per-system layout is the decision under test. `artifacts/<system>/<app>/`
exists so three scored systems can coexist -- without it the second system's
`evaluation.json` overwrites the first, and "scored by the unmodified harness"
stops being true. So these tests assert the path and assert that two systems do
not collide, not merely that a file appeared.

Everything is staged under `tmp_path` by `evaluate_helpers`; nothing here reads
the real `corpus/`.
"""

import pytest

import evaluate
import main
from evaluate_helpers import (
    ARTIFACTS_DIR_NAME,
    OTHER_SYSTEM,
    read_evaluation,
    run_evaluate,
    stage_artifacts,
    stage_corpus,
)
from evaluation.document import AGENTIC_AUDITOR, SCORED_SYSTEMS
from evaluation.harness import EVALUATION_NAME
from evaluation_fixtures import findings_document

# A value outside SCORED_SYSTEMS, shaped like the path it would become.
UNKNOWN_SYSTEM = "../etc"


def test_the_evaluation_is_written_under_the_system_directory(tmp_path, monkeypatch) -> None:
    """The layout is `<artifacts-dir>/<system>/evaluation.json`, not the bare directory."""
    stage_corpus(tmp_path, monkeypatch)
    artifacts_dir = stage_artifacts(tmp_path)
    assert run_evaluate(monkeypatch, artifacts_dir) == 0
    assert (artifacts_dir / AGENTIC_AUDITOR / EVALUATION_NAME).is_file()


def test_nothing_is_written_beside_the_system_directory(tmp_path, monkeypatch) -> None:
    """A file at `<artifacts-dir>/evaluation.json` is the path three systems would share."""
    stage_corpus(tmp_path, monkeypatch)
    artifacts_dir = stage_artifacts(tmp_path)
    run_evaluate(monkeypatch, artifacts_dir)
    assert not (artifacts_dir / EVALUATION_NAME).exists()


def test_two_systems_write_two_separate_evaluation_files(tmp_path, monkeypatch) -> None:
    """Both files survive the other run: the whole point of the system segment."""
    stage_corpus(tmp_path, monkeypatch)
    stage_artifacts(tmp_path, AGENTIC_AUDITOR)
    artifacts_dir = stage_artifacts(tmp_path, OTHER_SYSTEM, findings=findings_document())
    assert run_evaluate(monkeypatch, artifacts_dir) == 0
    assert run_evaluate(monkeypatch, artifacts_dir, OTHER_SYSTEM) == 0
    assert (artifacts_dir / AGENTIC_AUDITOR / EVALUATION_NAME).is_file()
    assert (artifacts_dir / OTHER_SYSTEM / EVALUATION_NAME).is_file()


def test_each_system_scores_its_own_findings_and_not_the_others(tmp_path, monkeypatch) -> None:
    """Distinct app directories, so one system's findings cannot be credited to another."""
    stage_corpus(tmp_path, monkeypatch)
    stage_artifacts(tmp_path, AGENTIC_AUDITOR)
    artifacts_dir = stage_artifacts(tmp_path, OTHER_SYSTEM, findings=findings_document())
    run_evaluate(monkeypatch, artifacts_dir)
    run_evaluate(monkeypatch, artifacts_dir, OTHER_SYSTEM)
    assert read_evaluation(artifacts_dir)["apps"][0]["true_positives"] == 1
    assert read_evaluation(artifacts_dir, OTHER_SYSTEM)["apps"][0]["true_positives"] == 0


def test_each_evaluation_records_the_system_it_scored(tmp_path, monkeypatch) -> None:
    """The label travels inside the record, so a row copied out of it keeps its system."""
    stage_corpus(tmp_path, monkeypatch)
    artifacts_dir = stage_artifacts(tmp_path, OTHER_SYSTEM, findings=findings_document())
    run_evaluate(monkeypatch, artifacts_dir, OTHER_SYSTEM)
    assert read_evaluation(artifacts_dir, OTHER_SYSTEM)["system"] == OTHER_SYSTEM


def test_two_runs_write_byte_identical_evaluations(tmp_path, monkeypatch) -> None:
    """A diff in `evaluation.json` must mean the score changed, never that it was rerun."""
    stage_corpus(tmp_path, monkeypatch)
    artifacts_dir = stage_artifacts(tmp_path)
    written = artifacts_dir / AGENTIC_AUDITOR / EVALUATION_NAME
    run_evaluate(monkeypatch, artifacts_dir)
    first = written.read_bytes()
    run_evaluate(monkeypatch, artifacts_dir)
    assert written.read_bytes() == first


def test_a_system_outside_the_closed_vocabulary_is_rejected(tmp_path, monkeypatch) -> None:
    """The value becomes a directory name, so argparse rejects it before a path is built."""
    with pytest.raises(SystemExit) as raised:
        run_evaluate(monkeypatch, tmp_path, UNKNOWN_SYSTEM)
    assert raised.value.code == 2


def test_the_rejected_system_is_never_created_as_a_directory(tmp_path, monkeypatch) -> None:
    """An unvalidated string would land in the filesystem, so nothing may be written first."""
    with pytest.raises(SystemExit):
        run_evaluate(monkeypatch, tmp_path / ARTIFACTS_DIR_NAME, UNKNOWN_SYSTEM)
    assert not (tmp_path / ARTIFACTS_DIR_NAME).exists()


@pytest.mark.parametrize("system", SCORED_SYSTEMS)
def test_every_scored_system_is_accepted_by_the_parser(system) -> None:
    """The vocabulary is `SCORED_SYSTEMS` itself, so adding a system needs no edit here."""
    assert evaluate.build_parser().parse_args(["--system", system]).system == system


def test_the_system_defaults_to_the_agentic_auditor() -> None:
    """Scoring this project's own output is the default, so the flag is optional."""
    assert evaluate.build_parser().parse_args([]).system == AGENTIC_AUDITOR


def test_the_auditors_default_artifacts_directory_is_named_for_the_auditor() -> None:
    """`main.py` writes the literal rather than importing it; the copy must still agree."""
    assert main.DEFAULT_ARTIFACTS_DIR.name == AGENTIC_AUDITOR


def test_the_auditors_default_sits_inside_the_directory_the_scorer_defaults_to() -> None:
    """So `evaluate` with no flags scores exactly where `main` with no flags wrote."""
    assert main.DEFAULT_ARTIFACTS_DIR == evaluate.DEFAULT_ARTIFACTS_DIR / AGENTIC_AUDITOR
