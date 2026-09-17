"""Brand marks are a second table, and what makes them a second table is asserted here.

`test_jsx_icon_names.py` asks whether the component can draw a name. This file
asks the other question: why `MARKS` is not simply more entries in `PATHS`.
Merging them is the plausible tidy-up and it would be wrong in a way nothing
else would report -- a filled 24-unit logo drawn through the line-icon branch
comes out as a stroked outline in the wrong box, which is not a crash and not a
blank, just a wrong-looking mark on a page nobody re-checks.

The three facts that make the split real, and all three are in the data rather
than in a branch someone has to remember:

- A line icon is a path string; a brand mark is an object with its own
  `viewBox`, because its author drew it in one and it is not ours to redraw.
- The line icons are stroked in `currentColor` with `fill="none"`; a mark is
  filled. Both spellings are in the component and both are checked, because a
  mark rendered with `fill="none"` is an empty outline.
- No name is in both tables. The component looks in `MARKS` first, so a name in
  both would make the `PATHS` entry unreachable -- dead data that
  `test_jsx_icon_names.py`'s "no dead entry" check would still pass, since the
  name *is* asked for.

Read as text through `icon_tables.py`, like every other sweep in this folder: no
node, no bundler, no fastapi. What it cannot see is what the browser draws --
that the mark is the GitHub logo, or that either path is valid SVG at all.
"""

import re

from .icon_tables import (
    ICON, brand_mark_names, brand_marks, icon_source, line_icon_names, marks_in)

# What a brand mark must carry, and the field that holds the drawing.
VIEWBOX_FIELD = "viewBox:"
PATH_FIELD = "d:"

# The viewBox every line icon shares. Hard-coded in the component rather than
# stored per entry, which is exactly the assumption a brand mark breaks.
LINE_ICON_VIEWBOX = 'viewBox="0 0 20 20"'

# How each table is painted. A mark is filled; a line icon is stroked and
# explicitly not filled, so it takes its colour from the text around it.
MARK_FILL = 'fill="currentColor"'
LINE_ICON_FILL = 'fill="none"'
LINE_ICON_STROKE = 'stroke="currentColor"'

# The lookup that runs first, which is what makes a shared name unreachable.
MARK_LOOKUP = "MARKS[name]"

# A floor: one mark today. Zero would satisfy every "each mark ..." check here.
LEAST_MARKS = 1

# A table of two written the way the component writes one, so the entry pattern
# is shown to parse rather than assumed to. The second entry carries no viewBox,
# which is the mistake the checks below exist to report.
PLANTED_TABLE = """
  wordmark: {
    viewBox: "0 0 24 24",
    d: "M0 0h24v24H0z",
  },
  logotype: {
    d: "M1 1h22v22H1z",
  },
"""
PLANTED_NAMES = ["logotype", "wordmark"]
PLANTED_WITHOUT_VIEWBOX = ["logotype"]


def marks_missing(field: str, marks: dict[str, str]) -> list[str]:
    """Every brand mark in a table that does not declare one required field."""
    return sorted(name for name, body in marks.items() if field not in body)


# --- the two tables are two ---------------------------------------------------

def test_the_component_really_declares_a_second_table() -> None:
    """Non-vacuity: with no marks read, every check below passes over an empty set."""
    assert len(brand_mark_names()) >= LEAST_MARKS


def test_no_name_is_in_both_tables() -> None:
    """`MARKS` is looked up first, so a shared name makes the `PATHS` entry unreachable."""
    assert sorted(line_icon_names() & brand_mark_names()) == []


def test_the_brand_marks_are_looked_up_before_the_line_icons() -> None:
    """Which is what makes the check above the right one to write."""
    source = icon_source()
    assert MARK_LOOKUP in source
    assert source.index(MARK_LOOKUP) < source.index("PATHS[name]")


# --- and each table carries what its own branch needs -------------------------

def test_every_brand_mark_brings_its_own_viewbox() -> None:
    """The reason for the split: a logo is drawn in the box its author drew it in."""
    assert marks_missing(VIEWBOX_FIELD, brand_marks()) == []


def test_every_brand_mark_brings_a_path_to_draw() -> None:
    """An entry with a viewBox and no `d` renders an empty box, which is the old defect."""
    assert marks_missing(PATH_FIELD, brand_marks()) == []


def test_the_entry_pattern_reads_a_table_of_more_than_one() -> None:
    """Planted: one real entry cannot show that a second would be read at all."""
    assert sorted(marks_in(PLANTED_TABLE)) == PLANTED_NAMES


def test_a_mark_with_no_viewbox_of_its_own_is_reported_by_name() -> None:
    """Mutation check: the check above returns an empty list either way, so plant one."""
    assert marks_missing(VIEWBOX_FIELD, marks_in(PLANTED_TABLE)) == PLANTED_WITHOUT_VIEWBOX


def test_the_line_icons_share_one_viewbox_the_component_writes_down() -> None:
    """They can, because they were all drawn to it -- and a mark could not."""
    assert LINE_ICON_VIEWBOX in icon_source()


def test_a_brand_mark_is_filled_and_a_line_icon_is_not() -> None:
    """A mark drawn with `fill="none"` is an outline of a logo, which is not the logo."""
    source = icon_source()
    assert MARK_FILL in source
    assert LINE_ICON_FILL in source
    assert LINE_ICON_STROKE in source


def test_the_two_tables_are_declared_separately_in_the_component() -> None:
    """Said last because it is the cheapest of these and the easiest to delete by accident."""
    assert len(re.findall(r"^const (PATHS|MARKS) = \{$", ICON.read_text(encoding="utf-8"),
                          re.MULTILINE)) == 2
