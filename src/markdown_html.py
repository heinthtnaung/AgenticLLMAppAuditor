"""Converts the Markdown this project writes into a standalone HTML page.

A deliberate subset converter, not a Markdown implementation. It handles
exactly what `report.py` and `remediation_report.py` emit -- headings, bullet
lists, fenced code, paragraphs, and three inline marks -- and it raises on a
construct it does not cover rather than flattening it into a paragraph, because
silently dropping a table out of a security report is worse than failing.

It escapes HTML rather than passing it through, and that is a safety property
rather than a limitation: part of its input is model-authored (`guidance` in
remediation.md, `narrative` in report.md), so a converter that let markup
through would let a local model put arbitrary HTML into a published document.
"""

import html
import re

FENCE = "```"
BULLET = "- "
MAX_HEADING = 6

INLINE_CODE = re.compile(r"`([^`]+)`")
BOLD = re.compile(r"\*\*(.+?)\*\*")
ITALIC = re.compile(r"\*(.+?)\*")

STYLE = """
:root { color-scheme: light dark; }
body { max-width: 46rem; margin: 2rem auto; padding: 0 1rem;
       font: 16px/1.6 system-ui, sans-serif; }
h1, h2, h3 { line-height: 1.25; }
h2 { margin-top: 2.5rem; border-bottom: 1px solid #8884; padding-bottom: .3rem; }
code { font-family: ui-monospace, monospace; font-size: .9em; }
pre { background: #8881; padding: .8rem; overflow-x: auto; border-radius: 4px; }
pre code { font-size: .85em; }
li { margin: .2rem 0; }
"""

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{style}</style>
</head>
<body>
{body}
</body>
</html>
"""


def inline(text: str) -> str:
    """Escape the text, then apply the three inline marks the reports use.

    Escaping comes first on purpose: the other order either double-escapes the
    entities it just wrote or lets a `<` through between two marks.
    """
    marked = html.escape(text, quote=False)
    marked = INLINE_CODE.sub(r"<code>\1</code>", marked)
    marked = BOLD.sub(r"<strong>\1</strong>", marked)
    return ITALIC.sub(r"<em>\1</em>", marked)


def _is_table_row(line: str) -> bool:
    """Say whether a line looks like a table row, which this subset does not render."""
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and len(stripped) > 1


def _starts_a_block(line: str) -> bool:
    """Say whether a line ends the paragraph before it by starting something else."""
    return (not line.strip() or line.startswith((FENCE, BULLET, "#"))
            or _is_table_row(line))


def _heading(line: str) -> str:
    """Render one ATX heading, keeping its level."""
    level = len(line) - len(line.lstrip("#"))
    if level > MAX_HEADING:
        raise ValueError(f"heading level {level} is deeper than HTML allows: {line!r}")
    return f"<h{level}>{inline(line[level:].strip())}</h{level}>"


def _code_block(lines: list[str], start: int, out: list[str]) -> int:
    """Render a fenced block verbatim and escaped, and return the line after it."""
    language = lines[start][len(FENCE):].strip()
    end = start + 1
    while end < len(lines) and not lines[end].startswith(FENCE):
        end += 1
    if end >= len(lines):
        raise ValueError("a fenced code block was opened and never closed")
    code = html.escape("\n".join(lines[start + 1:end]), quote=False)
    marked = f' class="language-{html.escape(language, quote=True)}"' if language else ""
    out.append(f"<pre><code{marked}>{code}</code></pre>")
    return end + 1


def _list_block(lines: list[str], start: int, out: list[str]) -> int:
    """Render one run of bullets as a list, and return the line after it."""
    end = start
    while end < len(lines) and lines[end].startswith(BULLET):
        end += 1
    items = "\n".join(f"<li>{inline(line[len(BULLET):])}</li>"
                      for line in lines[start:end])
    out.append(f"<ul>\n{items}\n</ul>")
    return end


def _paragraph(lines: list[str], start: int, out: list[str]) -> int:
    """Render one paragraph, joining its wrapped lines, and return the line after it."""
    end = start + 1
    while end < len(lines) and not _starts_a_block(lines[end]):
        end += 1
    joined = " ".join(line.strip() for line in lines[start:end])
    out.append(f"<p>{inline(joined)}</p>")
    return end


def _one_block(lines: list[str], index: int, out: list[str]) -> int:
    """Render the block starting at `index` and return where the next one starts."""
    line = lines[index]
    if not line.strip():
        return index + 1
    if line.startswith(FENCE):
        return _code_block(lines, index, out)
    if line.startswith(BULLET):
        return _list_block(lines, index, out)
    if _is_table_row(line):
        raise ValueError(
            f"this converter renders no tables, and will not flatten one into a "
            f"paragraph: {line.strip()!r}")
    if line.startswith("#"):
        out.append(_heading(line))
        return index + 1
    return _paragraph(lines, index, out)


def body_html(markdown_text: str) -> str:
    """Render every block of a Markdown document, in order."""
    lines = markdown_text.splitlines()
    out: list[str] = []
    index = 0
    while index < len(lines):
        index = _one_block(lines, index, out)
    return "\n".join(out)


def wrap_page(body: str, title: str) -> str:
    """Wrap rendered body HTML in a standalone page, so a browser can open it."""
    return PAGE.format(title=html.escape(title, quote=True), style=STYLE, body=body)


def to_html(markdown_text: str, title: str) -> str:
    """Convert one Markdown document into a whole standalone HTML page."""
    return wrap_page(body_html(markdown_text), title)
