"""A whole CLI run: the model writes remediation.json, and touches nothing else.

This is the structural property the design rests on. `findings.json` is the file
Phase 4 scores, and the model never writes into it -- its `model_run` stays
`disabled`, every `narrative` stays null, and the file is byte-identical whether
or not a model answered. The advice lands in a separate artifact the scorer
never opens.

Syft and the model are both stubbed, so this runs offline.
"""

from pathlib import Path

from artifacts.findings_document import MODEL_DISABLED, MODEL_UNAVAILABLE, MODEL_USED
from artifacts.remediation import UNAVAILABLE
from cli_helpers import (
    EMPTY_SCAN,
    STUB_MODEL_DIGEST,
    read_artifact,
    run_cli,
    stub_model,
    stub_model_unavailable,
    stub_syft,
)
from outputs import FINDINGS_NAME, REMEDIATION_NAME, REMEDIATION_REPORT_NAME
from remediation_report import render_from_files

APP_NAME = "advised-app"

# One privileged tool, so the run has a finding worth advising on.
APP_SOURCE = """from langchain_community.tools import ShellTool

tool = ShellTool()
"""


def build_app(tmp_path: Path) -> Path:
    """Write the one-file app every test below audits."""
    repo = tmp_path / APP_NAME
    repo.mkdir(exist_ok=True)
    (repo / "agent.py").write_text(APP_SOURCE, encoding="utf-8")
    return repo


def audit(monkeypatch, tmp_path: Path, artifacts_name: str = "artifacts") -> Path:
    """Run the CLI over that app and return the directory it wrote into."""
    stub_syft(monkeypatch, EMPTY_SCAN)
    artifacts = tmp_path / artifacts_name
    assert run_cli(monkeypatch, build_app(tmp_path), artifacts) == 0
    return artifacts / APP_NAME


def test_the_run_writes_the_remediation_artifact_and_its_report(monkeypatch, tmp_path) -> None:
    """Both land in the same per-app directory as the documents they were built from."""
    out = audit(monkeypatch, tmp_path)
    assert (out / REMEDIATION_NAME).is_file()
    assert (out / REMEDIATION_REPORT_NAME).is_file()


def test_findings_json_still_records_that_no_model_ran(monkeypatch, tmp_path) -> None:
    """The model advises; it does not detect. Every number Phase 4 scores stays static."""
    audit(monkeypatch, tmp_path)
    findings = read_artifact(tmp_path / "artifacts", APP_NAME, FINDINGS_NAME)
    assert findings["model_run"]["status"] == MODEL_DISABLED
    assert findings["model_run"]["model_identifier"] is None


def test_no_finding_carries_a_narrative_after_a_run_with_a_model(monkeypatch, tmp_path) -> None:
    """The one model-authored field on a record is left null, on every record."""
    audit(monkeypatch, tmp_path)
    findings = read_artifact(tmp_path / "artifacts", APP_NAME, FINDINGS_NAME)
    assert findings["finding_count"] > 0
    assert all(finding["narrative"] is None for finding in findings["findings"])


def test_findings_json_is_identical_whether_or_not_the_model_answered(
        monkeypatch, tmp_path) -> None:
    """The scored file cannot depend on a server being up; that is the whole layout."""
    answered = audit(monkeypatch, tmp_path, "answered")
    stub_model_unavailable(monkeypatch)
    silent = audit(monkeypatch, tmp_path, "silent")
    assert (answered / FINDINGS_NAME).read_text(encoding="utf-8") == (
        silent / FINDINGS_NAME).read_text(encoding="utf-8")


def test_the_remediation_artifact_holds_one_entry_per_finding(monkeypatch, tmp_path) -> None:
    """`advice_count` always equals findings.json's `finding_count`."""
    audit(monkeypatch, tmp_path)
    findings = read_artifact(tmp_path / "artifacts", APP_NAME, FINDINGS_NAME)
    remediation = read_artifact(tmp_path / "artifacts", APP_NAME, REMEDIATION_NAME)
    assert remediation["advice_count"] == findings["finding_count"]


def test_the_remediation_artifact_names_the_model_that_answered(monkeypatch, tmp_path) -> None:
    """A run that reached the server records which build wrote the words."""
    audit(monkeypatch, tmp_path)
    run = read_artifact(tmp_path / "artifacts", APP_NAME, REMEDIATION_NAME)["model_run"]
    assert run["status"] == MODEL_USED
    assert run["model_digest"] == STUB_MODEL_DIGEST


def test_an_unreachable_model_still_writes_both_remediation_files(
        monkeypatch, tmp_path) -> None:
    """Omitting the file would make "the server was down" look like "never run"."""
    stub_model_unavailable(monkeypatch)
    out = audit(monkeypatch, tmp_path)
    remediation = read_artifact(tmp_path / "artifacts", APP_NAME, REMEDIATION_NAME)
    assert remediation["model_run"]["status"] == MODEL_UNAVAILABLE
    assert remediation["status_counts"][UNAVAILABLE] == remediation["advice_count"] > 0
    assert (out / REMEDIATION_REPORT_NAME).is_file()


def test_the_remediation_report_is_the_rendering_of_the_two_artifacts(
        monkeypatch, tmp_path) -> None:
    """It is a reading of the files on disk, so re-rendering them must reproduce it exactly."""
    out = audit(monkeypatch, tmp_path)
    expected = render_from_files(APP_NAME, out / REMEDIATION_NAME, out / FINDINGS_NAME)
    assert (out / REMEDIATION_REPORT_NAME).read_text(encoding="utf-8") == expected


def test_the_written_advice_reaches_the_report(monkeypatch, tmp_path) -> None:
    """The stub answers cleanly, so a reader must find that advice on the page."""
    stub_model(monkeypatch)
    out = audit(monkeypatch, tmp_path)
    text = (out / REMEDIATION_REPORT_NAME).read_text(encoding="utf-8")
    assert "Treat the value as data rather than as instruction" in text
