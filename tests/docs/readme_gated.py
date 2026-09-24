"""The README's table of gated tests, the files that declare a flag, and ways to damage a row.

`README.md` under "Running the tests" names each file that skips unless a flag is
set, the flag, and how many tests the file holds. This reads that table.

**The rows are held to the files, not to themselves.** Every gated file declares
its flag as a module constant, the line `LIVE = "<FLAG>"`, and `live_flags` finds
the files that do. The table has to name exactly those files, each with the flag
it declares, so a row deleted or made unreadable, a gated file with no row, and
a flag misspelt all show up as a difference -- which reading only the rows the
pattern can find would miss. Discovery keys on that one convention; a file
gated some other way is not found.

The damage helpers derive each broken page from the parsed one, never from a
quoted string, so rewording the page cannot turn a guard's own test into a no-op.
"""

import re
from dataclasses import dataclass
from pathlib import Path

GATED_ROW = re.compile(
    r"^\| `(?P<flag>[A-Z_]+)=1` \| `(?P<path>tests/[^`]+\.py)`[^|]*\| (?P<count>\d+) \|",
    re.MULTILINE,
)
LIVE_DECLARATION = re.compile(r'^LIVE = "(?P<flag>[A-Z_]+)"$', re.MULTILINE)
TESTS_FOLDER = "tests"


@dataclass(frozen=True)
class GatedRow:
    """One row of the table: the flag, the file it runs, and how many tests the page says."""

    flag: str
    path: str
    count: int


def rows_on(page: str) -> list[GatedRow]:
    """Read every row of the table that the row pattern can read."""
    return [row_of(one) for one in GATED_ROW.finditer(page)]


def row_of(read: re.Match) -> GatedRow:
    """Give one row the row pattern matched."""
    return GatedRow(read["flag"], read["path"], int(read["count"]))


def table_of(page: str) -> dict[str, str]:
    """Give each file the page's table names, with the flag it names for it."""
    return {row.path: row.flag for row in rows_on(page)}


def live_flags(root: Path) -> dict[str, str]:
    """Give each test file under `root` that declares its flag, by its path from `root`."""
    files = sorted((root / TESTS_FOLDER).rglob("*.py"))
    declared = [(path, LIVE_DECLARATION.search(path.read_text(encoding="utf-8"))) for path in files]
    return {path.relative_to(root).as_posix(): read["flag"] for path, read in declared if read}


def switched_on(flag: str) -> str:
    """Give a flag as a reader types it to run its file."""
    return f"{flag}=1"


def names_flag(reason: str, flag: str) -> bool:
    """Say whether a skip reason names this flag exactly, as the command a reader would type."""
    # A whole word: `LIVE_SCAN=1` sits inside `SYFT_LIVE_SCAN=1` and names another flag.
    return re.search(rf"(?<![A-Z_]){re.escape(switched_on(flag))}\b", reason) is not None


def without_row(page: str, row: GatedRow) -> str:
    """Take one row off the page."""
    opening = f"| `{switched_on(row.flag)}`"
    return "\n".join(line for line in page.split("\n") if not line.startswith(opening))


def unquoted(page: str, row: GatedRow) -> str:
    """Drop the backticks from one row's flag, so the row pattern cannot read it."""
    return page.replace(f"`{switched_on(row.flag)}`", switched_on(row.flag))


def misnamed(page: str, row: GatedRow) -> str:
    """Name one row's flag by its first words only, which the right flag still contains."""
    return page.replace(f"`{switched_on(row.flag)}`", f"`{switched_on(shortened(row.flag))}`")


def suffixed(page: str, row: GatedRow) -> str:
    """Name one row's flag by its last words only, which the right flag still contains."""
    return page.replace(f"`{switched_on(row.flag)}`", f"`{switched_on(trailing(row.flag))}`")


def shortened(flag: str) -> str:
    """Give a flag without its last word, a wrong name that is a prefix of the right one."""
    return flag.rsplit("_", 1)[0]


def trailing(flag: str) -> str:
    """Give a flag without its first word, a wrong name that is a suffix of the right one."""
    return flag.split("_", 1)[-1]
