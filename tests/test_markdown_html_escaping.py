"""HTML in the Markdown is escaped, never passed through. The converter's one security property.

Part of the input is model-authored -- `guidance` in remediation.md and
`narrative` in report.md come from a local model reading an audited repository,
which may itself contain injected text. A converter that let markup through
would let that path put arbitrary HTML, and therefore script, into a document a
supervisor opens in a browser.

So every planted payload below is a real one: a script tag and an `onerror`
image, in each of the three places report text can appear. They must come out
as characters on the page, never as elements in it.
"""

from reporting.markdown_html import body_html, to_html

SCRIPT = "<script>alert(1)</script>"
IMAGE = '<img src=x onerror="alert(1)">'

ESCAPED_SCRIPT = "&lt;script&gt;alert(1)&lt;/script&gt;"


def test_a_script_tag_in_a_paragraph_is_escaped() -> None:
    """Planted: the commonest payload there is, in ordinary report prose."""
    html = body_html(f"the model wrote {SCRIPT}")
    assert ESCAPED_SCRIPT in html
    assert "<script>" not in html


def test_an_onerror_image_in_a_paragraph_is_escaped() -> None:
    """Planted: the payload that needs no script tag, so a tag filter would miss it."""
    html = body_html(f"the model wrote {IMAGE}")
    assert "<img" not in html
    assert "&lt;img" in html


def test_a_script_tag_in_a_bullet_is_escaped() -> None:
    """The gap list and the advice list are bullets, and both carry model prose."""
    html = body_html(f"- {SCRIPT}")
    assert ESCAPED_SCRIPT in html
    assert "<script>" not in html


def test_an_onerror_image_in_a_bullet_is_escaped() -> None:
    """Same payload, same place a finding's evidence is written."""
    html = body_html(f"- {IMAGE}")
    assert "<img" not in html
    assert "&lt;img" in html


def test_a_script_tag_in_a_fenced_code_block_is_escaped() -> None:
    """A quoted snippet of the audited app is the likeliest place to find real markup."""
    html = body_html(f"```html\n{SCRIPT}\n```")
    assert ESCAPED_SCRIPT in html
    assert "<script>" not in html


def test_an_onerror_image_in_a_fenced_code_block_is_escaped() -> None:
    """Verbatim means the characters are kept, not that the browser runs them."""
    html = body_html(f"```html\n{IMAGE}\n```")
    assert "<img" not in html
    assert "&lt;img" in html


def test_a_script_tag_in_a_heading_is_escaped() -> None:
    """A heading is the one line a model can influence that also becomes a bookmark."""
    html = body_html(f"## {SCRIPT}")
    assert "<script>" not in html


def test_escaping_happens_before_the_inline_marks_are_applied() -> None:
    """The other order double-escapes the entities it just wrote, or lets a `<` through."""
    assert body_html("**<b>x</b>**") == "<p><strong>&lt;b&gt;x&lt;/b&gt;</strong></p>"


def test_markup_inside_inline_code_is_escaped_too() -> None:
    """<code> is still HTML: an unescaped tag inside it is an element like any other."""
    assert body_html("`<b>x</b>`") == "<p><code>&lt;b&gt;x&lt;/b&gt;</code></p>"


def test_an_ampersand_is_escaped_so_the_entity_it_starts_is_not_read() -> None:
    """Escaping `<` alone is not enough: `&lt;` written literally must stay literal."""
    assert body_html("a &lt; b") == "<p>a &amp;lt; b</p>"


def tags(html: str) -> list[str]:
    """Every `<...>` the rendered HTML contains, so a planted one shows up as an extra."""
    return [f"<{part.split('>')[0]}>" for part in html.split("<")[1:]]


def test_the_only_tags_in_the_output_are_the_ones_the_converter_wrote() -> None:
    """Whole-document check: a payload in every block, and no element from any of them."""
    html = body_html(f"# {SCRIPT}\n\n{IMAGE}\n\n- {SCRIPT}\n\n```\n{IMAGE}\n```")
    written = {"<h1>", "</h1>", "<p>", "</p>", "<ul>", "</ul>", "<li>", "</li>",
               "<pre>", "</pre>", "<code>", "</code>"}
    assert set(tags(html)) == written


def test_a_title_holding_markup_is_escaped_into_the_page() -> None:
    """The title is attribute-adjacent text, so it is escaped with quotes as well."""
    page = to_html("hello", 'Report "one" <b>')
    assert "<title>Report &quot;one&quot; &lt;b&gt;</title>" in page
