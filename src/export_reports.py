"""Exports the two Markdown reports an audit wrote as HTML and PDF.

A command of its own, run after an audit rather than inside it, for two
reasons: an audit stays fast and needs no renderer installed, and the artifact
count `outputs.write_all` reports keeps meaning what it meant.

One chain, never two: Markdown -> HTML -> PDF. The Markdown the audit already
wrote is the single source, so nothing here re-reads findings.json and becomes
a second producer of the same prose.

PDF needs a Unicode font, and this project commits no binaries -- so one is
looked for on the machine and the PDF is skipped when there is none, exactly as
a missing Syft yields no bill of materials. The HTML never depends on it.
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fpdf import FPDF

from reporting import markdown_html

REPORT_STEM = "report"
REMEDIATION_STEM = "remediation"
MARKDOWN_SUFFIX = ".md"
HTML_SUFFIX = ".html"
PDF_SUFFIX = ".pdf"

TITLES = {REPORT_STEM: "Audit report", REMEDIATION_STEM: "How to fix what was found"}

# Fixed on purpose, and the Unix epoch so no reader mistakes it for a fact:
# every PDF writer stamps a creation time, and a real one would make two
# identical exports differ, which is the one thing artifacts here may not do.
PINNED_CREATION_DATE = datetime(1970, 1, 1, tzinfo=timezone.utc)

BODY_FAMILY = "body"
MONO_FAMILY = "mono"
BASE_FONT_SIZE = 11

# Where a Unicode TTF usually lives. Looked up rather than committed: a font is
# a 750 KB binary, and this project keeps binaries out of the repository.
FONT_DIRECTORIES = (
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/TTF"),
    Path("/usr/local/share/fonts"),
    Path("/Library/Fonts"),
)

# DejaVu Sans ships no oblique face, so italic reuses the upright one: emphasis
# in these reports is carried by wording rather than by slant.
BODY_FILES = {
    "": "DejaVuSans.ttf", "B": "DejaVuSans-Bold.ttf",
    "I": "DejaVuSans.ttf", "BI": "DejaVuSans-Bold.ttf",
}
MONO_FILES = {
    "": "DejaVuSansMono.ttf", "B": "DejaVuSansMono-Bold.ttf",
    "I": "DejaVuSansMono-Oblique.ttf", "BI": "DejaVuSansMono-BoldOblique.ttf",
}

NO_FONT_REASON = (
    "no Unicode TTF found in " + ", ".join(str(d) for d in FONT_DIRECTORIES) +
    " (on Debian or Ubuntu: sudo apt install fonts-dejavu-core)")
NO_RENDERER_REASON = "fpdf2 is not installed - see requirements.txt"


def font_directory() -> Path | None:
    """Return the first directory holding every font face needed, or None."""
    wanted = set(BODY_FILES.values()) | set(MONO_FILES.values())
    return next((path for path in FONT_DIRECTORIES
                 if path.is_dir() and all((path / name).is_file() for name in wanted)),
                None)


def _new_document(fonts: Path) -> "FPDF":
    """Start a PDF with the fonts registered and every varying field pinned."""
    from fpdf import FPDF

    pdf = FPDF()
    # Uncompressed so the file is inspectable and its outline stays plain text.
    # Body text is *not* greppable even so: a Unicode report needs an embedded
    # TrueType subset, which draws two-byte glyph ids under Identity-H rather
    # than letters. A test asserting a sentence reached the page decodes the
    # /ToUnicode table; one asserting a heading may read the outline directly.
    pdf.set_compression(False)
    pdf.set_creation_date(PINNED_CREATION_DATE)
    pdf.set_producer(None)
    pdf.set_creator(None)
    for family, files in ((BODY_FAMILY, BODY_FILES), (MONO_FAMILY, MONO_FILES)):
        for style, name in files.items():
            pdf.add_font(family, style, fonts / name)
    pdf.set_font(BODY_FAMILY, size=BASE_FONT_SIZE)
    pdf.add_page()
    return pdf


def to_pdf(body: str, fonts: Path) -> bytes:
    """Render rendered body HTML as PDF bytes, identical for identical input.

    Body only: fpdf2 parses a fragment, and handing it a whole page makes it
    complain about the <head> it has no use for.
    """
    from fpdf.fonts import FontFace

    mono = FontFace(family=MONO_FAMILY)
    pdf = _new_document(fonts)
    pdf.write_html(body, font_family=BODY_FAMILY,
                   tag_styles={"code": mono, "pre": mono})
    return bytes(pdf.output())


def export_one(source: Path, title: str, fonts: Path | None) -> list[Path]:
    """Write the HTML beside one Markdown report, and the PDF too when it can."""
    body = markdown_html.body_html(source.read_text(encoding="utf-8"))
    page = markdown_html.wrap_page(body, title)
    # Both payloads before either write, so a refusal on the second cannot
    # leave the first on disk and unreported.
    document = None if fonts is None else to_pdf(body, fonts)
    html_path = source.with_suffix(HTML_SUFFIX)
    html_path.write_text(page, encoding="utf-8")
    if document is None:
        return [html_path]
    pdf_path = source.with_suffix(PDF_SUFFIX)
    pdf_path.write_bytes(document)
    return [html_path, pdf_path]


def pdf_reason(fonts: Path | None) -> str:
    """Say why no PDF will be written, or nothing when one will."""
    try:
        import fpdf  # noqa: F401
    except ImportError:
        return NO_RENDERER_REASON
    return "" if fonts else NO_FONT_REASON


def _try_one(source: Path, title: str, fonts: Path | None,
             notes: list[str]) -> list[Path]:
    """Export one report, recording a refusal rather than losing the other document.

    The converter refuses a construct it cannot render, and `guidance` is
    model-authored -- so one sentence in the advice must not be able to stop
    the audit report, which is deterministic and refusal-free by construction.
    """
    try:
        return export_one(source, title, fonts)
    except ValueError as error:
        notes.append(f"{source.name} was not converted: {error}")
        return []


def export_all(app_dir: Path) -> tuple[list[Path], str]:
    """Export every report in one app's artifact directory, and say what was skipped."""
    if not app_dir.is_dir():
        raise NotADirectoryError(f"cannot export {app_dir}: not a directory")
    fonts = font_directory()
    reason = pdf_reason(fonts)
    sources = [(app_dir / f"{stem}{MARKDOWN_SUFFIX}", title)
               for stem, title in sorted(TITLES.items())
               if (app_dir / f"{stem}{MARKDOWN_SUFFIX}").is_file()]
    if not sources:
        raise FileNotFoundError(
            f"no report to export in {app_dir}: expected "
            f"{REPORT_STEM}{MARKDOWN_SUFFIX} or {REMEDIATION_STEM}{MARKDOWN_SUFFIX}")
    notes: list[str] = []
    written: list[Path] = []
    for source, title in sources:
        written += _try_one(source, title, None if reason else fonts, notes)
    if not written:
        raise ValueError("no report could be converted: " + "; ".join(notes))
    return written, "; ".join(part for part in [reason, *notes] if part)


def build_parser() -> argparse.ArgumentParser:
    """Describe the command line arguments."""
    parser = argparse.ArgumentParser(
        description="Export an audit's Markdown reports as HTML and PDF.")
    parser.add_argument(
        "app_dir", type=Path,
        help="an app's artifact directory, e.g. artifacts/agentic_auditor/<app>")
    return parser


def main() -> int:
    """Export one app's reports. Returns the process exit code."""
    args = build_parser().parse_args()
    try:
        written, reason = export_all(args.app_dir)
    except (NotADirectoryError, FileNotFoundError, ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for path in written:
        print(f"wrote {path}")
    if reason:
        print(f"  no PDF: {reason}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
