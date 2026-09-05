"""Exporting an audit's Markdown as HTML and PDF, and what happens when it cannot.

The input is the Markdown the audit already wrote, so these tests render both
reports through their real producers rather than inventing prose. That is what
lets the last two tests assert the property that matters: the "What was not
examined" section keeps its billing all the way to the page a reader opens. A
findings list that arrives without it reads as a clean bill.

The PDF needs a Unicode font that is not committed, so every PDF test is skipped
when the machine has none -- visibly, and naming what to install, exactly as the
exporter itself degrades.

The staged advice carries a written entry citing a passage, so the conversion
of a `Grounded on` list is exercised rather than assumed: the citations are a
flat bullet list because `markdown_html.py` reads a bullet only at column zero,
and an indented one fell through to a paragraph here and shipped its `- ` marks
as text into the HTML and the PDF. The last section is what stops that
recurring.
"""

import re
from pathlib import Path

import pytest

import export_reports
from reporting import remediation_report
from reporting import report
from findings_fixtures import build_document, static_finding
from pdf_text import drawn_text
from remediation_fixtures import remediation_document, source, written_entry
from report_fixtures import APP, NOT_EXAMINED_HEADING, surfaces_document

# Words no report writes, so the PDF reader can be shown not to invent them.
ABSENT_SENTENCE = "Every risk class was checked and the application is safe."

FONTS = export_reports.font_directory()
needs_font = pytest.mark.skipif(FONTS is None, reason=export_reports.NO_FONT_REASON)


def advised() -> tuple[dict, dict]:
    """One finding and the grounded advice written for it, both through their real producers."""
    findings = build_document([static_finding()])
    entry = written_entry(findings["findings"][0]["finding_id"], sources=[source()])
    return remediation_document([entry]), findings


def stage_reports(app_dir: Path) -> None:
    """Write both reports into an artifact directory, through the renderers an audit uses.

    Two findings documents on purpose. The audit report is staged with none,
    because its tests turn on "no findings" keeping the caveat that qualifies
    it; the remediation report is staged with one that carries advice and a
    citation, because an empty document renders only the "nothing to fix" block
    and left every line of advice unconverted. The exporter reads the Markdown
    and never joins the two, so the pair cannot disagree about anything.
    """
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "report.md").write_text(
        report.render(APP, build_document([]), surfaces_document()), encoding="utf-8")
    remediation, findings = advised()
    (app_dir / "remediation.md").write_text(
        remediation_report.render(APP, remediation, findings), encoding="utf-8")


def exported(tmp_path: Path, name: str = "app") -> tuple[Path, tuple[list[Path], str]]:
    """Stage both reports in a fresh directory and export them."""
    app_dir = tmp_path / name
    stage_reports(app_dir)
    return app_dir, export_reports.export_all(app_dir)


# --- What it refuses ----------------------------------------------------------

def test_a_directory_with_no_report_is_refused(tmp_path) -> None:
    """Writing nothing and saying nothing would look exactly like a finished export."""
    with pytest.raises(FileNotFoundError, match="no report to export"):
        export_reports.export_all(tmp_path)


def test_the_refusal_names_the_files_it_looked_for(tmp_path) -> None:
    """A reader needs to know which two names the exporter expected to find."""
    with pytest.raises(FileNotFoundError, match="report.md or remediation.md"):
        export_reports.export_all(tmp_path)


def test_a_path_that_is_a_file_is_refused(tmp_path) -> None:
    """The argument is an app's artifact directory; a file is a mistyped one."""
    not_a_directory = tmp_path / "report.md"
    not_a_directory.write_text("# One\n", encoding="utf-8")
    with pytest.raises(NotADirectoryError, match="not a directory"):
        export_reports.export_all(not_a_directory)


def test_a_directory_that_does_not_exist_is_refused(tmp_path) -> None:
    """A path typed wrong must fail, never be created and exported as empty."""
    with pytest.raises(NotADirectoryError, match="not a directory"):
        export_reports.export_all(tmp_path / "nowhere")


# --- The HTML, which never depends on a font -----------------------------------

def test_both_reports_are_exported(tmp_path) -> None:
    """An audit writes two documents, so an export that produced one is incomplete."""
    app_dir, (written, _) = exported(tmp_path)
    assert app_dir / "report.html" in written
    assert app_dir / "remediation.html" in written


def test_the_html_is_a_whole_page_a_browser_can_open(tmp_path) -> None:
    """A fragment is not a document: the export exists to be opened, not embedded."""
    app_dir, _ = exported(tmp_path)
    page = (app_dir / "report.html").read_text(encoding="utf-8")
    assert page.startswith("<!DOCTYPE html>")
    assert f"<title>{export_reports.TITLES['report']}</title>" in page


def test_the_html_is_written_when_no_font_is_available(tmp_path, monkeypatch) -> None:
    """The PDF degrades; the HTML does not. A missing font must not cost both."""
    monkeypatch.setattr(export_reports, "font_directory", lambda: None)
    app_dir, (written, _) = exported(tmp_path)
    assert written == [app_dir / "remediation.html", app_dir / "report.html"]
    assert not (app_dir / "report.pdf").exists()


def test_a_skipped_pdf_says_why_and_what_to_install(tmp_path, monkeypatch) -> None:
    """Silence would read as "no PDF was wanted" rather than "no font was found"."""
    monkeypatch.setattr(export_reports, "font_directory", lambda: None)
    _, (_, reason) = exported(tmp_path)
    assert reason == export_reports.NO_FONT_REASON
    assert "fonts-dejavu-core" in reason


def test_a_reason_is_given_exactly_when_a_pdf_is_missing(tmp_path) -> None:
    """No skip goes unexplained, and no explanation is given for a skip that did not happen."""
    _, (written, reason) = exported(tmp_path)
    assert bool(reason) == ([path for path in written if path.suffix == ".pdf"] == [])


# --- The PDF --------------------------------------------------------------------

@needs_font
def test_the_pdf_is_written_beside_the_html(tmp_path) -> None:
    """Both formats land next to the Markdown they were rendered from."""
    app_dir, (written, reason) = exported(tmp_path)
    assert reason == ""
    assert app_dir / "report.pdf" in written


@needs_font
def test_two_exports_produce_byte_identical_pdfs(tmp_path) -> None:
    """A creation date left to the clock would make every export differ from the last."""
    first, _ = exported(tmp_path, "first")
    second, _ = exported(tmp_path, "second")
    assert (first / "report.pdf").read_bytes() == (second / "report.pdf").read_bytes()


@needs_font
def test_the_pdf_creation_date_is_pinned_to_a_fixed_instant(tmp_path) -> None:
    """Pinned to the epoch on purpose, so no reader mistakes the stamp for a fact."""
    app_dir, _ = exported(tmp_path, "dated")
    assert b"/CreationDate (D:19700101" in (app_dir / "report.pdf").read_bytes()


# --- The gap list survives the conversion ------------------------------------------

def test_the_gap_section_survives_into_the_html(tmp_path) -> None:
    """Put the findings first and the gaps nowhere and the conversion undoes the report."""
    app_dir, _ = exported(tmp_path)
    page = (app_dir / "report.html").read_text(encoding="utf-8")
    assert "<h2>What was not examined</h2>" in page
    assert report.NOTHING_FOUND in page


def test_the_gap_section_keeps_the_rank_the_findings_have_in_the_html(tmp_path) -> None:
    """Equal billing is a heading level; an <h3> here would read as an appendix."""
    app_dir, _ = exported(tmp_path)
    page = (app_dir / "report.html").read_text(encoding="utf-8")
    assert page.index("<h2>Findings</h2>") < page.index("<h2>What was not examined</h2>")


@needs_font
def test_the_gap_heading_is_greppable_in_the_raw_pdf_bytes(tmp_path) -> None:
    """The PDF is written uncompressed, so its outline names the section in plain text."""
    app_dir, _ = exported(tmp_path)
    assert NOT_EXAMINED_HEADING.lstrip("# ").encode() in (app_dir / "report.pdf").read_bytes()


@needs_font
def test_the_gap_section_survives_into_the_pdf(tmp_path) -> None:
    """The section is drawn on the page, not merely listed in the bookmarks."""
    app_dir, _ = exported(tmp_path)
    drawn = drawn_text((app_dir / "report.pdf").read_bytes())
    assert "What was not examined" in drawn


@needs_font
def test_the_nothing_found_warning_survives_into_the_pdf(tmp_path) -> None:
    """"No findings" without the sentence that qualifies it is the misreading to prevent."""
    app_dir, _ = exported(tmp_path)
    assert report.NOTHING_FOUND in drawn_text((app_dir / "report.pdf").read_bytes())


@needs_font
def test_the_pdf_reader_finds_no_sentence_the_report_never_wrote(tmp_path) -> None:
    """Guard: a decoder that returned everything would make the two tests above vacuous."""
    app_dir, _ = exported(tmp_path)
    assert ABSENT_SENTENCE not in drawn_text((app_dir / "report.pdf").read_bytes())


# --- The advice survives the conversion --------------------------------------------

def remediation_page(tmp_path: Path) -> str:
    """Export both reports and return the advice as the HTML a reader opens."""
    app_dir, _ = exported(tmp_path)
    return (app_dir / "remediation.html").read_text(encoding="utf-8")


def test_the_advice_the_model_wrote_reaches_the_html(tmp_path) -> None:
    """A conversion that dropped the prose would leave a report of findings and no fixes."""
    remediation, findings = advised()
    assert remediation["advice"][0]["guidance"] in remediation_page(tmp_path)


def test_a_citation_is_converted_into_a_list_item(tmp_path) -> None:
    """The `Grounded on` block is a bullet list, and must arrive as one rather than as prose."""
    lists = re.findall(r"<ul>.*?</ul>", remediation_page(tmp_path), re.DOTALL)
    assert [block for block in lists if source()["url"] in block]


def test_no_paragraph_in_the_converted_advice_carries_a_bullet_marker(tmp_path) -> None:
    """A literal `- ` inside a <p> is the bug this section exists to catch."""
    paragraphs = re.findall(r"<p>.*?</p>", remediation_page(tmp_path), re.DOTALL)
    assert not [block for block in paragraphs if "- " in block]


@needs_font
def test_a_citation_reaches_the_pdf_page(tmp_path) -> None:
    """The attribution is what makes a quoted passage citable, so it may not stop at the HTML."""
    app_dir, _ = exported(tmp_path)
    assert source()["path"] in drawn_text((app_dir / "remediation.pdf").read_bytes())
