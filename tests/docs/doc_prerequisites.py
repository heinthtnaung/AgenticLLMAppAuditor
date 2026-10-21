"""The Python version the docs promise and `pyproject.toml` requires, read so they cannot drift.

The minimum sat at 3.10 though only 3.11 was ever tested, because nothing tied
the "Minimum" cell of the prerequisites tables to pyproject's `requires-python`,
nor either of those to the "Tested with" version in the same row. These helpers
read all three as a bare `X.Y`, so a test can hold them equal and a revert to a
minimum the project no longer tests turns red rather than passing in silence.

`python_row` refuses a table with no `| Python |` row and `lower_bound` refuses a
requirement that is not a `>=X.Y` lower bound. Either would fail the check anyway,
as an opaque `TypeError` or `AttributeError`; the guards replace that with a
message naming what could not be read.
"""

import re
import tomllib

from doc_pages import PROJECT_ROOT, Page

PYPROJECT = PROJECT_ROOT / "pyproject.toml"

# The columns of a prerequisites row, `| Tool | For | Tested with | Minimum |`.
TOOL, TESTED_WITH, MINIMUM = 0, 2, 3
PYTHON_TOOL = "Python"

# A bare `major.minor`, the form every version is compared as.
MAJOR_MINOR = re.compile(r"\d+\.\d+")
# `requires-python` as a lower bound and nothing else, `>=X.Y`.
LOWER_BOUND = re.compile(r">=(\d+\.\d+)")


def major_minor(version: str) -> str:
    """Give the leading `X.Y` of a version string, raising if it carries none."""
    match = MAJOR_MINOR.match(version.strip())
    if not match:
        raise ValueError(f"{version!r} has no leading 'X.Y' version to read")
    return match.group()


def table_cells(line: str) -> list[str]:
    """Give a Markdown table row as its stripped cells, or an empty list if it is not one."""
    if not line.lstrip().startswith("|"):
        return []
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def python_row(page: Page) -> tuple[str, str]:
    """Give the Python row's 'Tested with' cell and its Minimum as a bare 'X.Y'."""
    for line in page.text.splitlines():
        cells = table_cells(line)
        if len(cells) > MINIMUM and cells[TOOL] == PYTHON_TOOL:
            return cells[TESTED_WITH], major_minor(cells[MINIMUM])
    raise ValueError(
        f"{page.document.path} has no '| {PYTHON_TOOL} | ... |' prerequisites row with a "
        "Minimum, so there is no stated minimum to check"
    )


def required_python() -> str:
    """Give `pyproject.toml`'s requires-python as 'X.Y'."""
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    return lower_bound(project["requires-python"])


def lower_bound(requirement: str) -> str:
    """Give the 'X.Y' of a '>=X.Y' requirement, raising on any other form."""
    match = LOWER_BOUND.fullmatch(requirement.strip())
    if not match:
        raise ValueError(
            f"requires-python is {requirement!r}, not a '>=X.Y' lower bound this check can read"
        )
    return match.group(1)
