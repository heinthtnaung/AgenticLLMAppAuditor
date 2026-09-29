"""The filter bars the script wires: a segmented tag filter, a search box, a toggle-all.

One place for the controls the Overview table, the Council list and the Inventory
share, so the class names and data attributes the script reads are written once.

**They do nothing until the script runs, so the stylesheet hides them without it.**
With no JavaScript the full list shows and a dead filter bar would only mislead;
`html:not(.js) .toolbar { display: none }` keeps it off the page until it works.
"""

from dataclasses import dataclass

from report.html_layout import tag, text


@dataclass(frozen=True)
class Segment:
    """One button of a segmented filter: the tag it shows, its label and its count."""

    tag: str
    label: str
    count: int


def toolbar(host_id: str, controls: str) -> str:
    """Give the bar the script reads by `data-filter-for`, wrapping its controls."""
    counter = tag("span", "", "result-count")
    return f'<div class="toolbar" data-filter-for="{text(host_id)}">{controls}{counter}</div>'


def segmented(segments: tuple[Segment, ...]) -> str:
    """Give the segmented filter: one button per tag, the first pressed by default."""
    buttons = "".join(segment_button(one, at == 0) for at, one in enumerate(segments))
    return f'<div class="seg" role="group">{buttons}</div>'


def segment_button(segment: Segment, pressed: bool) -> str:
    """Give one filter button, carrying the tag it filters on and its count."""
    count = tag("span", text(segment.count), "n")
    aria = "true" if pressed else "false"
    return (
        f'<button type="button" data-filter="{text(segment.tag)}" aria-pressed="{aria}">'
        f"{text(segment.label)}{count}</button>"
    )


def search_box(label: str, placeholder: str = "Search") -> str:
    """Give the search input the script filters by, with a screen-reader label and a hint."""
    named = tag("span", text(label), "sr")
    field = f'<input type="search" data-search placeholder="{text(placeholder)}">'
    return f'<label class="search">{named}{field}</label>'


def toggle_all_button(host_id: str, more: str, less: str) -> str:
    """Give the button the script opens or closes every `details.metric` in a host with."""
    return (
        f'<button type="button" class="toggle-all" data-toggle-all="{text(host_id)}" '
        f'data-open="false" data-more="{text(more)}" data-less="{text(less)}">{text(more)}</button>'
    )


def empty_line(said: str) -> str:
    """Give the note the script shows when a filter leaves a list empty, hidden until then."""
    return f'<p class="empty" hidden>{text(said)}</p>'
