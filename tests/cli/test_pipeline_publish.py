"""`publish` degrades with a printed reason, and never swallows a real failure.

The VEX emitter, the exporter and the AI-formatted view are stubbed at their
module seams, so no test here needs vexctl, a renderer, a font or a model --
and none starts a process.

Three stages, degrading on different terms, which is why each has tests of its
own below: a missing prerequisite for VEX is a note, a vexctl that errors is
fatal, and the AI page is a bonus whose every failure is a note.
"""

import pytest

import pipeline
from ai_report import AI_REPORT_NAME
from emit_vex import DOCUMENT_NAME, PROGRAM_NAME
from pipeline_helpers import stub_ai_report, stub_export, stub_vex

APP = "demo"
EXPORT_NOTE = "no Unicode TTF found"


def test_no_advisory_data_skips_vex_and_still_exports(monkeypatch, tmp_path, capsys) -> None:
    """An audit that read no advisories publishes a note on stderr, never a VEX."""
    emitted = stub_vex(monkeypatch)
    exported = stub_export(monkeypatch)
    stub_ai_report(monkeypatch)
    pipeline.publish(tmp_path / APP, advisories_read=False)
    assert "no VEX: this audit read no advisory data" in capsys.readouterr().err
    assert emitted == []
    assert exported == [tmp_path / APP]


def test_a_missing_vexctl_skips_vex_and_still_exports(monkeypatch, tmp_path, capsys) -> None:
    """vexctl absent is a prerequisite note on stderr; emit never runs, export does."""
    emitted = stub_vex(monkeypatch, available=False)
    exported = stub_export(monkeypatch)
    stub_ai_report(monkeypatch)
    pipeline.publish(tmp_path / APP, advisories_read=True)
    assert f"no VEX: {PROGRAM_NAME} is not installed" in capsys.readouterr().err
    assert emitted == []
    assert exported == [tmp_path / APP]


def test_a_written_vex_document_is_reported(monkeypatch, tmp_path, capsys) -> None:
    """When emit answers a path, publish prints where the document went."""
    document = tmp_path / APP / DOCUMENT_NAME
    stub_vex(monkeypatch, written=document)
    stub_export(monkeypatch)
    stub_ai_report(monkeypatch)
    pipeline.publish(tmp_path / APP, advisories_read=True)
    assert f"wrote {document}" in capsys.readouterr().out


def test_nothing_to_state_is_a_note_not_a_failure(monkeypatch, tmp_path, capsys) -> None:
    """emit answering None means no advisory findings, said in so many words."""
    stub_vex(monkeypatch, written=None)
    stub_export(monkeypatch)
    stub_ai_report(monkeypatch)
    pipeline.publish(tmp_path / APP, advisories_read=True)
    assert "no VEX: no advisory findings" in capsys.readouterr().out


def test_a_failing_vexctl_propagates(monkeypatch, tmp_path) -> None:
    """vexctl installed but erroring is unexplained, so it raises rather than degrades."""
    stub_vex(monkeypatch, error=RuntimeError(f"{PROGRAM_NAME} create failed: boom"))
    exported = stub_export(monkeypatch)
    with pytest.raises(RuntimeError, match="create failed"):
        pipeline.publish(tmp_path / APP, advisories_read=True)
    assert exported == []


def test_exported_paths_are_printed_and_the_reason_surfaced(monkeypatch, tmp_path,
                                                            capsys) -> None:
    """Every written report is named on stdout; a non-empty reason goes to stderr."""
    html, pdf = tmp_path / APP / "report.html", tmp_path / APP / "report.pdf"
    stub_vex(monkeypatch)
    stub_export(monkeypatch, written=(html, pdf), reason=EXPORT_NOTE)
    stub_ai_report(monkeypatch)
    pipeline.publish(tmp_path / APP, advisories_read=False)
    printed = capsys.readouterr()
    assert f"wrote {html}" in printed.out
    assert f"wrote {pdf}" in printed.out
    assert f"export note: {EXPORT_NOTE}" in printed.err


def test_an_empty_export_reason_prints_no_note(monkeypatch, tmp_path, capsys) -> None:
    """A full export has nothing to explain, so nothing about it reaches stderr."""
    stub_vex(monkeypatch)
    stub_export(monkeypatch, written=(tmp_path / APP / "report.html",), reason="")
    stub_ai_report(monkeypatch)
    pipeline.publish(tmp_path / APP, advisories_read=False)
    assert "export note" not in capsys.readouterr().err


def test_the_ai_formatted_page_is_reported(monkeypatch, tmp_path, capsys) -> None:
    """The last stage writes a page, so publish names it beside the other outputs."""
    stub_vex(monkeypatch)
    stub_export(monkeypatch)
    formatted = stub_ai_report(monkeypatch)
    pipeline.publish(tmp_path / APP, advisories_read=False)
    assert f"wrote {tmp_path / APP / AI_REPORT_NAME}" in capsys.readouterr().out
    assert formatted == [tmp_path / APP]


def test_an_unreachable_model_makes_the_ai_page_a_note(monkeypatch, tmp_path, capsys) -> None:
    """The authoritative report is already written, so no model is no failure."""
    stub_vex(monkeypatch)
    exported = stub_export(monkeypatch)
    stub_ai_report(monkeypatch, error=RuntimeError("cannot reach the local model server"))
    pipeline.publish(tmp_path / APP, advisories_read=False)
    assert "no AI report: cannot reach the local model server" in capsys.readouterr().err
    assert exported == [tmp_path / APP], "the export ran before the bonus stage and stands"


def test_a_page_that_fails_verification_is_a_note_not_a_failure(monkeypatch, tmp_path,
                                                                capsys) -> None:
    """The security-relevant refusal: a page inventing an advisory is dropped, not shipped.

    `ai_report.build_page` raises ValueError when the model's page names an
    advisory the report does not. Losing the view is the right outcome; losing
    the run would make the optional stage able to fail an audit.
    """
    stub_vex(monkeypatch)
    stub_export(monkeypatch)
    stub_ai_report(monkeypatch, error=ValueError("page names advisories not in the report"))
    pipeline.publish(tmp_path / APP, advisories_read=False)
    assert "no AI report: page names advisories not in the report" in capsys.readouterr().err
