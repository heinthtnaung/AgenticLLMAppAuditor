"""The CLI writes report.md beside the JSON, rendered from the files it just wrote.

The report is the only artifact a person reads, and it is produced last, from
the two documents already on disk. These tests hold that it is written at all,
that it is the rendering of those documents rather than a second telling of the
run, and that a finding the audit produced reaches it.

Syft is stubbed, so this runs offline.
"""

from pathlib import Path

from checks.permissions import OWASP_ID as PERMISSION_RISK, TITLE as PERMISSION_TITLE
from cli_helpers import EMPTY_SCAN, run_cli, stub_syft
from outputs import FINDINGS_NAME, REPORT_NAME, SURFACES_NAME
from reporting.report import NOTHING_FOUND, render_from_files

APP_NAME = "report-app"

# One privileged tool, so the run has a finding for the report to render.
APP_SOURCE = """from langchain_community.tools import ShellTool

tool = ShellTool()
"""


def audit(monkeypatch, tmp_path: Path) -> Path:
    """Run the CLI over a one-file app and return the directory it wrote into."""
    stub_syft(monkeypatch, EMPTY_SCAN)
    repo = tmp_path / APP_NAME
    repo.mkdir()
    (repo / "agent.py").write_text(APP_SOURCE, encoding="utf-8")
    assert run_cli(monkeypatch, repo, tmp_path / "artifacts") == 0
    return tmp_path / "artifacts" / APP_NAME


def test_report_md_is_written_beside_the_json_artifacts(monkeypatch, tmp_path) -> None:
    """It lands in the same per-app directory as the documents it was rendered from."""
    out = audit(monkeypatch, tmp_path)
    assert (out / REPORT_NAME).is_file()
    assert (out / FINDINGS_NAME).is_file()
    assert (out / SURFACES_NAME).is_file()


def test_the_written_report_opens_with_the_heading_naming_the_app(monkeypatch, tmp_path) -> None:
    """An empty or truncated file would still be written; the heading says it was rendered."""
    text = (audit(monkeypatch, tmp_path) / REPORT_NAME).read_text(encoding="utf-8")
    assert text.startswith(f"# Audit report: {APP_NAME}")


def test_the_written_report_renders_the_findings_the_run_produced(monkeypatch, tmp_path) -> None:
    """The privileged tool the checks found is in the report, not only in findings.json."""
    text = (audit(monkeypatch, tmp_path) / REPORT_NAME).read_text(encoding="utf-8")
    assert f"### {PERMISSION_RISK} — {PERMISSION_TITLE}" in text
    assert NOTHING_FOUND not in text


def test_the_written_report_is_the_rendering_of_the_two_artifacts(monkeypatch, tmp_path) -> None:
    """It is a reading of the files on disk, so re-rendering them must reproduce it exactly."""
    out = audit(monkeypatch, tmp_path)
    expected = render_from_files(APP_NAME, out / FINDINGS_NAME, out / SURFACES_NAME)
    assert (out / REPORT_NAME).read_text(encoding="utf-8") == expected
