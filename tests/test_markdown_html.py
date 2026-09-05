"""What the Markdown-to-HTML converter renders, and what it refuses outright.

It is a deliberate subset, not a Markdown implementation, so these tests are
written against the constructs `report.py` and `remediation_report.py` actually
emit. The refusals matter as much as the renderings: this converter raises on a
construct it does not cover rather than flattening it into a paragraph, because
a table silently dropped out of a security report is worse than a failed export.

The escaping half -- the security property, since part of the input is
model-authored -- is in test_markdown_html_escaping.py.
"""

import pytest

from markdown_html import body_html, to_html

TITLE = "Audit report"


# --- The three inline marks --------------------------------------------------

def test_double_stars_become_strong() -> None:
    """`report.py` bolds the lead of every gap sentence, so bold has to render."""
    assert body_html("a **bold** word") == "<p>a <strong>bold</strong> word</p>"


def test_single_stars_become_emphasis() -> None:
    """The other star mark must not be swallowed by the bold rule that runs first."""
    assert body_html("a *quiet* word") == "<p>a <em>quiet</em> word</p>"


def test_backticks_become_code() -> None:
    """File paths and identifiers are written in backticks throughout both reports."""
    assert body_html("see `app/agent.py`") == "<p>see <code>app/agent.py</code></p>"


# --- Blocks -------------------------------------------------------------------

def test_headings_render_at_levels_one_to_three() -> None:
    """The reports use exactly three depths, and the level carries their billing."""
    assert body_html("# One\n## Two\n### Three") == "<h1>One</h1>\n<h2>Two</h2>\n<h3>Three</h3>"


def test_a_heading_deeper_than_html_allows_is_refused() -> None:
    """There is no <h7>, so a seventh hash is a mistake to report, not to render."""
    with pytest.raises(ValueError, match="deeper than HTML allows"):
        body_html("####### seven")


def test_a_run_of_bullets_becomes_one_list() -> None:
    """One <ul> per run: a list per line would read as three separate lists."""
    assert body_html("- one\n- two\n- three") == (
        "<ul>\n<li>one</li>\n<li>two</li>\n<li>three</li>\n</ul>")


def test_two_runs_of_bullets_separated_by_a_paragraph_stay_two_lists() -> None:
    """The gap list and the audit summary are separate lists and must not merge."""
    html = body_html("- one\n\nbetween\n\n- two")
    assert html.count("<ul>") == 2
    assert "<p>between</p>" in html


def test_a_paragraph_joins_the_lines_it_was_wrapped_across() -> None:
    """Markdown wraps prose at the column; HTML must show one sentence, not two lines."""
    assert body_html("a wrapped\nsentence") == "<p>a wrapped sentence</p>"


def test_a_blank_line_starts_a_new_paragraph() -> None:
    """Two paragraphs in the Markdown have to stay two paragraphs in the page."""
    assert body_html("first\n\nsecond") == "<p>first</p>\n<p>second</p>"


# --- Fenced code ---------------------------------------------------------------

def test_a_fenced_block_keeps_its_language_as_a_class() -> None:
    """The language is evidence about the snippet, so it survives into the page."""
    assert 'class="language-python"' in body_html("```python\npass\n```")


def test_a_fenced_block_with_no_language_gets_no_class() -> None:
    """An empty class attribute would claim a language the Markdown never named."""
    assert body_html("```\npass\n```") == "<pre><code>pass</code></pre>"


def test_a_fenced_block_keeps_its_contents_verbatim() -> None:
    """A snippet quoted as evidence is worthless if its indentation is reflowed."""
    assert body_html("```python\ndef run():\n    return 1\n```") == (
        '<pre><code class="language-python">def run():\n    return 1</code></pre>')


def test_a_fence_that_is_never_closed_is_refused() -> None:
    """Reading to the end of the file would swallow the rest of the report in silence."""
    with pytest.raises(ValueError, match="opened and never closed"):
        body_html("```python\ndef run():")


# --- What it will not render ----------------------------------------------------

def test_a_table_row_is_refused_rather_than_flattened() -> None:
    """A table quietly turned into a paragraph loses the rows a reader would act on."""
    with pytest.raises(ValueError, match="renders no tables"):
        body_html("| package | version |")


def test_the_table_refusal_quotes_the_row_it_would_not_render() -> None:
    """The message has to say which line stopped the export, or nobody can fix it."""
    with pytest.raises(ValueError, match="package"):
        body_html("| package | version |")


# --- The whole page ---------------------------------------------------------------

def test_to_html_produces_a_standalone_page() -> None:
    """A browser needs a document, not a fragment: doctype, head and body."""
    page = to_html("# One", TITLE)
    assert page.startswith("<!DOCTYPE html>")
    assert "<body>" in page and "</html>" in page


def test_the_page_carries_the_title_it_was_given() -> None:
    """Two exported reports sit in one directory, so each tab has to name itself."""
    assert f"<title>{TITLE}</title>" in to_html("# One", TITLE)


def test_the_page_holds_the_rendered_body() -> None:
    """The wrapper must not be testable without the content it is wrapping."""
    assert "<h1>One</h1>" in to_html("# One", TITLE)
