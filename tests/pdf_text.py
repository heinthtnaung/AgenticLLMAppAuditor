"""Recovers the words an exported PDF draws, so a test can prove a section survived.

`export_reports` writes the PDF uncompressed on purpose, but uncompressed is not
the same as greppable. The reports need a Unicode font, and an embedded TrueType
subset stores glyph ids rather than letters, so a sentence a reader sees on the
page appears nowhere in the file as ASCII -- only the outline titles do. This
reads the /ToUnicode table the same file carries and turns the ids back.

Knowingly small, and a test helper rather than a PDF reader: it handles exactly
what fpdf2 writes -- a `beginbfchar` table per embedded subset, no bfranges, and
the four escapes `fpdf.util.escape_parens` applies. It decodes every text run
under every table, because which table belongs to which run would mean reading
the page's resource dictionary, and a run decoded under the wrong font comes out
as nonsense rather than as a false match.
"""

import re

BFCHAR_TABLE = re.compile(rb"beginbfchar(.*?)endbfchar", re.DOTALL)
HEX_PAIR = re.compile(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>")

# A PDF string followed by the operator that draws it.
SHOW_TEXT = re.compile(rb"\((?:[^()\\]|\\.)*\)\s*Tj")
ESCAPE = re.compile(rb"\\(.)", re.DOTALL)
ESCAPED = {b"\\": b"\\", b"(": b"(", b")": b")", b"r": b"\r"}

# Stands in for a glyph the table being tried does not define, so decoding a run
# under the wrong font cannot join two fragments into a phrase nobody wrote.
UNKNOWN_GLYPH = "�"


def _glyph_tables(pdf: bytes) -> list[dict[int, str]]:
    """One glyph-id to character table per embedded font subset."""
    return [{int(glyph, 16): bytes.fromhex(point.decode()).decode("utf-16-be")
             for glyph, point in HEX_PAIR.findall(block)}
            for block in BFCHAR_TABLE.findall(pdf)]


def _unescape(raw: bytes) -> bytes:
    """Undo the four escapes fpdf2 applies when it writes a PDF string."""
    return ESCAPE.sub(lambda match: ESCAPED.get(match.group(1), match.group(1)), raw)


def _text_runs(pdf: bytes) -> list[bytes]:
    """The glyph ids of every run of text the file draws."""
    return [_unescape(match.group(0).rsplit(b")", 1)[0][1:])
            for match in SHOW_TEXT.finditer(pdf)]


def _decode(run: bytes, table: dict[int, str]) -> str:
    """Turn one run's two-byte glyph ids back into characters."""
    ids = (int.from_bytes(run[at:at + 2], "big") for at in range(0, len(run) - 1, 2))
    return "".join(table.get(glyph, UNKNOWN_GLYPH) for glyph in ids)


def drawn_text(pdf: bytes) -> str:
    """Every run of text the PDF draws, one per line, decoded under each font in turn."""
    runs = _text_runs(pdf)
    if not runs:
        raise ValueError("no text was found in the PDF, so it can prove nothing")
    return "\n".join(_decode(run, table) for table in _glyph_tables(pdf) for run in runs)
