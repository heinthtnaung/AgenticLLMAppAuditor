"""`publish` degrades with a printed reason, and never swallows a real failure.

The VEX emitter and the exporter are stubbed at their module seams, so no test
here needs vexctl, a renderer or a font -- and none starts a process.

Two stages, degrading on different terms, which is why each has tests of its
own below: a missing prerequisite for VEX is a note, a vexctl that errors is
fatal, and a partial export is a note beside the reports it did write.
"""

import pytest

import pipeline
from emit_vex import DOCUMENT_NAME, PROGRAM_NAME
from pipeline_helpers import stub_export, stub_vex

APP = "demo"
EXPORT_NOTE = "no Unicode TTF found"


def test_no_advisory_data_skips_vex_and_still_exports(monkeypatch, tmp_path, capsys) -> None:
    """An audit that read no advisories publishes a note on stderr, never a VEX."""
    emitted = stub_vex(monkeypatch)
    exported = stub_export(monkeypatch)
    pipeline.publish(tmp_path / APP, advisories_read=False)
    assert "no VEX: this audit read no advisory data" in capsys.readouterr().err
    assert emitted == []
    assert exported == [tmp_path / APP]


def test_a_missing_vexctl_skips_vex_and_still_exports(monkeypatch, tmp_path, capsys) -> None:
    """vexctl absent is a prerequisite note on stderr; emit never runs, export does."""
    emitted = stub_vex(monkeypatch, available=False)
    exported = stub_export(monkeypatch)
    pipeline.publish(tmp_path / APP, advisories_read=True)
    assert f"no VEX: {PROGRAM_NAME} is not installed" in capsys.readouterr().err
    assert emitted == []
    assert exported == [tmp_path / APP]


def test_a_written_vex_document_is_reported(monkeypatch, tmp_path, capsys) -> None:
    """When emit answers a path, publish prints where the document went."""
    document = tmp_path / APP / DOCUMENT_NAME
    stub_vex(monkeypatch, written=document)
    stub_export(monkeypatch)
    pipeline.publish(tmp_path / APP, advisories_read=True)
    assert f"wrote {document}" in capsys.readouterr().out


def test_nothing_to_state_is_a_note_not_a_failure(monkeypatch, tmp_path, capsys) -> None:
    """emit answering None means no advisory findings, said in so many words."""
    stub_vex(monkeypatch, written=None)
    stub_export(monkeypatch)
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
    pipeline.publish(tmp_path / APP, advisories_read=False)
    printed = capsys.readouterr()
    assert f"wrote {html}" in printed.out
    assert f"wrote {pdf}" in printed.out
    assert f"export note: {EXPORT_NOTE}" in printed.err


def test_an_empty_export_reason_prints_no_note(monkeypatch, tmp_path, capsys) -> None:
    """A full export has nothing to explain, so nothing about it reaches stderr."""
    stub_vex(monkeypatch)
    stub_export(monkeypatch, written=(tmp_path / APP / "report.html",), reason="")
    pipeline.publish(tmp_path / APP, advisories_read=False)
    assert "export note" not in capsys.readouterr().err
