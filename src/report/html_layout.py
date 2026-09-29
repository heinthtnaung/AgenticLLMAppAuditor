"""The markup the HTML rendering shares: escaping, elements, chips and badges.

Everything that reaches the page goes through `text`, because a vector, a path
and an advisory summary all arrive from outside this tool and any of them can
carry a `<`. No colour is named here; `report.html_style` owns those, so a value
the palette cannot reach is one file's problem rather than every component's.

**`number` formats and never rounds.** The record's figures are the engine's
answers, and a rendering that rounded one would be a second place a number could
differ from the record it exists to show.

**A CVSS chip and an Organisation Risk chip are two shapes on two scales.**
`scored_chip` writes the scale on every one, because two bare numbers in two
bands read as one number somebody got wrong -- `docs/SCORING_MODEL.md` refuses
to merge the two claims.
"""

from html import escape

from report.council_beside import CouncilFigure
from report.html_style import band_class

SEPARATOR = '<span class="separator">·</span>'
CVSS_SCALE = "cvss"


def text(value: object) -> str:
    """Escape one value for the page, so nothing a scanner read can close a tag."""
    return escape(str(value), quote=True)


def number(value: float) -> str:
    """Give a number exactly as the record carries it, never rounded and never recomputed."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"A number on the page must be a number, not {type(value).__name__}")
    return str(value)


def tag(name: str, content: str, css_class: str = "") -> str:
    """Wrap already-escaped content in one element, with a class when it has one."""
    named = f' class="{css_class}"' if css_class else ""
    return f"<{name}{named}>{content}</{name}>"


# The external-link mark, an inline SVG so it fetches nothing: no src, no xlink:href,
# no external URL, only path data drawn in the current text colour.
EXTERNAL_ICON = (
    '<svg class="ext" viewBox="0 0 12 12" aria-hidden="true" focusable="false">'
    '<path d="M4.5 2H2v8h8V7.5M7 2h3v3M10 2 5.5 6.5" fill="none" stroke="currentColor" '
    'stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


def external_link(address: str, content: str) -> str:
    """Link already-escaped content to an advisory a reader may open, marked as leaving the page."""
    # No referrer: a report served from an internal host would otherwise hand its
    # own address, repository name and all, to whichever advisory site is opened.
    # It opens in a new tab, as the redesign template has it, and this page fetches
    # nothing itself -- a reader follows the link or does not.
    opened = f'<a href="{text(address)}" target="_blank" rel="noreferrer">'
    return f'{opened}{content}{EXTERNAL_ICON}</a>'


def listing(items: list[str], css_class: str = "") -> str:
    """Put already-rendered items in a list, so no caller loops inside a loop."""
    return tag("ul", "".join(tag("li", item) for item in items), css_class)


def separated(parts: list[str]) -> str:
    """Join fragments with the dot the terminal rendering puts between them."""
    return SEPARATOR.join(part for part in parts if part)


def group(title: str, lede: str, body: str) -> str:
    """Head a group inside a panel with its title and the line saying what it holds."""
    if not body:
        return ""
    said = tag("p", text(lede), "fine") if lede else ""
    head = tag("div", tag("h2", text(title)) + said, "section-head")
    return head + body


def panel_head(title: str, lede: str = "") -> str:
    """Head a tab panel with its title and, where it has one, the line saying what it holds."""
    said = tag("p", text(lede), "fine") if lede else ""
    return tag("div", tag("h2", text(title)) + said, "panel-head")


def empty_note(said: str) -> str:
    """Say a panel or list holds nothing, rather than leaving it blank."""
    return tag("p", text(said), "note")


def badge(label: str, kind: str) -> str:
    """Give one pill badge in a named tone -- alarm, ok or muted."""
    return tag("span", text(label), f"badge badge-{kind}")


def cell(label: str, content: str) -> str:
    """Give one table cell, labelled so a phone can read the row stacked."""
    return f'<td data-label="{text(label)}">{content}</td>'


def jump(target: str, content: str, css_class: str = "goto") -> str:
    """Link already-rendered content to another place on this page, which the script scrolls to."""
    return f'<a class="{css_class}" href="#{text(target)}">{content}</a>'


def scored_chip(scale: str, value: str, band: str, css_class: str) -> str:
    """Show one score with the scale it is on and the band it lands in.

    The scale is on the chip and not only in the heading above it. A published
    CVSS score and an Organisation Risk Score are two different claims about one
    finding -- `docs/SCORING_MODEL.md` refuses to merge them -- and two bare
    numbers in two bands read as one number somebody got wrong.
    """
    labelled = tag("span", text(scale), "scale") + tag("span", value, "value")
    banded = labelled + tag("span", text(band), "band")
    return tag("span", banded, f"{css_class} {band_class(band)}")


def mini_chip(source: str, value: str, band: str, css_class: str) -> str:
    """Show one source's score in a table cell: the source, the number and the band."""
    named = tag("span", text(source), "src") + tag("span", value, "value")
    banded = named + tag("span", text(band), "band")
    return tag("span", banded, f"mini {css_class} {band_class(band)}")


def figure_chip(figure: CouncilFigure) -> str:
    """Show a council's figure on a CVSS chip, the shape every published score takes."""
    return scored_chip(CVSS_SCALE, number(figure.base_score), figure.band, "cvss")
