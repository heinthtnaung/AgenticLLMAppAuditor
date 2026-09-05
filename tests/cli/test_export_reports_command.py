"""One report refusing must not cost the other, and what the command prints.

Separate from test_export_reports.py, which covers the conversion itself. The
first pair here is the important one: `guidance` is model-authored, so a table
a model writes must not be able to stop the deterministic audit report from
being exported alongside it.
"""

import pytest

import export_reports
from report_fixtures import APP
from test_export_reports import stage_reports



GUIDANCE_TABLE = "| option | effect |\n| --- | --- |\n| pin it | fixes it |"


def test_a_table_in_the_advice_does_not_stop_the_audit_report(tmp_path) -> None:
    """`guidance` is model-authored, so one sentence in it must not cost both documents.

    The converter refuses a table rather than flattening one out of a security
    report, which is right -- but `remediation.md` sorts first, so before this
    was isolated a single model-written table left neither document exported.
    """
    app_dir = tmp_path / "tabled"
    stage_reports(app_dir)
    (app_dir / "remediation.md").write_text(
        f"# How to fix what was found: {APP}\n\n### LLM01\n\n{GUIDANCE_TABLE}\n",
        encoding="utf-8")

    written, reason = export_reports.export_all(app_dir)

    assert (app_dir / "report.html") in written, "the audit report must still be written"
    assert not (app_dir / "remediation.html").exists()
    assert "remediation.md was not converted" in reason
    assert "renders no tables" in reason


def test_every_report_refusing_is_still_an_error(tmp_path) -> None:
    """Isolating the two must not turn "nothing was exported" into a silent success."""
    app_dir = tmp_path / "all-tabled"
    app_dir.mkdir(parents=True)
    (app_dir / "report.md").write_text(f"# Audit report: {APP}\n\n{GUIDANCE_TABLE}\n",
                                       encoding="utf-8")
    with pytest.raises(ValueError, match="no report could be converted"):
        export_reports.export_all(app_dir)


# --- The command itself ------------------------------------------------------

def test_the_export_command_exits_zero_and_lists_what_it_wrote(
        capsys, monkeypatch, tmp_path) -> None:
    """The happy path returns 0 and names every file, so a user knows what appeared."""
    app_dir = tmp_path / "commanded"
    stage_reports(app_dir)
    monkeypatch.setattr("sys.argv", ["export_reports.py", str(app_dir)])
    assert export_reports.main() == 0
    assert "report.html" in capsys.readouterr().out


def test_the_export_command_says_on_stderr_why_no_pdf_was_written(
        capsys, monkeypatch, tmp_path) -> None:
    """A skipped PDF is reported, not silently absent, and it names what to install."""
    app_dir = tmp_path / "fontless"
    stage_reports(app_dir)
    monkeypatch.setattr(export_reports, "font_directory", lambda: None)
    monkeypatch.setattr("sys.argv", ["export_reports.py", str(app_dir)])
    assert export_reports.main() == 0
    assert "no PDF" in capsys.readouterr().err
    assert not (app_dir / "report.pdf").exists()


def test_the_export_command_reports_a_missing_directory_as_an_exit_code(
        capsys, monkeypatch, tmp_path) -> None:
    """Something the user can fix prints a message and exits 1 rather than raising."""
    monkeypatch.setattr("sys.argv", ["export_reports.py", str(tmp_path / "absent")])
    assert export_reports.main() == 1
    assert "not a directory" in capsys.readouterr().err
