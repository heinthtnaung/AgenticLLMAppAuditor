"""The tab bar and the panels it switches between, and how each reads without JS.

**Readable with scripts off.** Every panel is a plain `<section>` that shows by
default; only the `js` class the script adds turns the bar into tabs and hides
the inactive panels. With no script the bar is hidden and the panels stack, so
nothing on the page is ever unreachable.

Each tab routes over `[role="tab"]` by `aria-controls`, the contract the script
reads. A count rides on the tab, marked as an alarm where it is one a reader
should not scroll past.
"""

from dataclasses import dataclass

from report.html_layout import tag, text

TABLIST = '<div class="tabs" role="tablist">'


@dataclass(frozen=True)
class Panel:
    """One tab and the panel it controls: its name, label, body, count and tone."""

    name: str
    label: str
    body: str
    count: int | None = None
    alarm: bool = False


def tabbar(panels: tuple[Panel, ...]) -> str:
    """Give the sticky bar of tabs, one per panel, in the order they are listed."""
    links = "".join(tab_link(one) for one in panels)
    return tag("nav", tag("div", TABLIST + links + "</div>", "wrap"), "tabbar")


def tab_link(panel: Panel) -> str:
    """Give one tab: an anchor to its panel, carrying its count where it has one."""
    attrs = (
        f'id="tab-{panel.name}" class="tab" role="tab" href="#{panel.name}" '
        f'data-tab="{panel.name}" aria-controls="panel-{panel.name}"'
    )
    return f"<a {attrs}>{text(panel.label)}{count_badge(panel)}</a>"


def count_badge(panel: Panel) -> str:
    """Give the count that rides on a tab, marked as an alarm where it is one."""
    if panel.count is None:
        return ""
    tone = "n alarm" if panel.alarm and panel.count else "n"
    return tag("span", text(panel.count), tone)


def panels_main(panels: tuple[Panel, ...]) -> str:
    """Put every panel in the page's `main`, each a section a tab controls."""
    return tag("main", "".join(panel_section(one) for one in panels), "wrap")


def panel_section(panel: Panel) -> str:
    """Give one panel as a labelled tab panel, shown by default and hidden only by the script."""
    opened = (
        f'<section id="panel-{panel.name}" class="panel" role="tabpanel" '
        f'aria-labelledby="tab-{panel.name}">'
    )
    return f"{opened}{panel.body}</section>"
