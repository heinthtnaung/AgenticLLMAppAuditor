"""The markup the HTML rendering shares: escaping, elements, and a titled block.

Everything that reaches the page goes through `text`, because a vector, a path
and an advisory summary all arrive from outside this tool and any of them can
carry a `<`. No colour is named here; `report.html_style` owns those, so a value
the palette cannot reach is one file's problem rather than every component's.

**`number` formats and never rounds.** The record's figures are the engine's
answers, and a rendering that rounded one would be a second place a number could
differ from the record it exists to show.
"""

from html import escape

from report.html_style import band_class

SEPARATOR = '<span class="separator">·</span>'


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


def listing(items: list[str], css_class: str = "") -> str:
    """Put already-rendered items in a list, so no caller loops inside a loop."""
    return tag("ul", "".join(tag("li", item) for item in items), css_class)


def separated(parts: list[str]) -> str:
    """Join fragments with the dot the terminal rendering puts between them."""
    return SEPARATOR.join(part for part in parts if part)


def section(title: str, lede: str, body: str) -> str:
    """Put a titled block on the page, with the line saying what it holds."""
    if not body:
        return ""
    said = tag("p", text(lede), "lede") if lede else ""
    return tag("section", tag("h2", text(title)) + said + body)


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
