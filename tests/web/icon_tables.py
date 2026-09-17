"""Reads the two tables `Icon.jsx` draws from: line icons, and brand marks.

There are two on purpose and they are read as two here. `PATHS` holds the
hand-drawn line icons -- every one a 20-unit viewBox stroked in `currentColor`,
so a token change recolours the set -- and `MARKS` holds filled brand marks,
each in the viewBox its author drew it in and none of them ours to redraw. The
component branches on which table a name is in, so a test that merged them
would be checking a shape the component does not have.

Shared by the two files that check them: `test_jsx_icon_names.py`, whose subject
is the names the page asks for, and `test_jsx_icon_marks.py`, whose subject is
what keeps the second table apart from the first. One reader, for the reason
`jsx_sweep.py` and `css_rules.py` are each one reader -- two would drift into
two ideas of what an entry is.

A text scan, like every other sweep in this folder: no node, no bundler, no
JavaScript parser. What it cannot see is an entry written in a shape these
patterns do not match, which is why both callers assert the tables are non-empty
before asserting anything about their contents.
"""

import re
from pathlib import Path

from .jsx_sweep import strip_comments

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
ICON = FRONTEND_SRC / "components" / "Icon.jsx"

# The two tables, each read to its own closing brace at column zero.
PATHS_BLOCK = re.compile(r"const PATHS = \{(.*?)\n\};", re.DOTALL)
MARKS_BLOCK = re.compile(r"const MARKS = \{(.*?)\n\};", re.DOTALL)

# A line icon is `name: "path"`, one per line. A brand mark is `name: { ... }`,
# so its key is matched together with the brace that opens its body -- otherwise
# the fields *inside* it would read as three more icons.
PATHS_KEY = re.compile(r"^\s*([A-Za-z_]\w*):", re.MULTILINE)
MARK_ENTRY = re.compile(r"^  ([A-Za-z_]\w*): \{(.*?)^  \},", re.DOTALL | re.MULTILINE)


def icon_source() -> str:
    """The icon component's own source, with its comments stripped."""
    return strip_comments(ICON.read_text(encoding="utf-8"))


def _block(pattern: re.Pattern, table: str) -> str:
    """One table's body as text, insisting the component still declares it."""
    found = pattern.search(icon_source())
    assert found, f"{ICON.name} declares no {table} table"
    return found.group(1)


def line_icon_names() -> set[str]:
    """Every name the stroked `PATHS` table has a path for."""
    keys = set(PATHS_KEY.findall(_block(PATHS_BLOCK, "PATHS")))
    assert keys, f"{ICON.name}'s PATHS table has no entry this test can read"
    return keys


def marks_in(block: str) -> dict[str, str]:
    """Every top-level entry of a `MARKS` body, name to the body it declares.

    Takes the text rather than reading the file, so a caller can plant a table
    and check that this really parses one instead of trusting it.
    """
    return dict(MARK_ENTRY.findall(block))


def brand_marks() -> dict[str, str]:
    """Every entry of the filled `MARKS` table the component ships."""
    found = marks_in(_block(MARKS_BLOCK, "MARKS"))
    assert found, f"{ICON.name}'s MARKS table has no entry this test can read"
    return found


def brand_mark_names() -> set[str]:
    """Just the names of the brand marks, without the bodies."""
    return set(brand_marks())


def icon_names() -> set[str]:
    """Every name `<Icon name=...>` can draw, from whichever table holds it."""
    return line_icon_names() | brand_mark_names()
