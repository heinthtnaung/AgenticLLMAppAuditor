"""The results-checking section, held to the code it points a reader at.

`README.md` names, for each result, the file whose rule checks it, and the
council vector row counts the CVSS metrics. Both are read off the code here
rather than pasted, so a section that points at a file that is gone, a row with
its `Where` cell turned to prose, a dropped row, or "all seven metrics" turns
this red.
"""

import re

from cvss.metrics import METRIC_ORDER
from doc_pages import README, read

HEADING = "## How the results are checked"
NEXT_HEADING = "## Learn more"
# A backtick-quoted path to a Python source, as the table's `Where` column writes it.
SOURCE_PATH = re.compile(r"`([\w./]+\.py)`")
# Seven rows name eleven source paths: four rows name two files, three name one.
# Dropping a row or prosing a `Where` cell takes the count below this.
LEAST_PATHS = 11
# Spelled-out counts indexed by the number, for the metric count in the vector row.
NUMBER_WORDS = (
    "zero", "one", "two", "three", "four", "five", "six",
    "seven", "eight", "nine", "ten", "eleven", "twelve",
)


def section(text: str) -> str:
    """Give the results-checking section, from its heading to the next one."""
    start = text.index(HEADING)
    return text[start : text.index(NEXT_HEADING, start)]


def test_the_section_is_on_the_page():
    """A deleted or renamed section would take the whole check off the page in silence."""
    assert HEADING in read(README).text


def test_every_source_the_table_points_to_exists():
    """Each file the `Where` column names is a real source, so a moved file is caught."""
    paths = SOURCE_PATH.findall(section(read(README).text))
    assert len(paths) >= LEAST_PATHS
    missing = [path for path in paths if not (README.path.parent / path).exists()]
    assert not missing, f"the section points at files that are gone: {missing}"


def test_the_vector_row_counts_every_cvss_metric():
    """The vector stands on all eight metrics, so the row names that count, not another."""
    phrase = f"{NUMBER_WORDS[len(METRIC_ORDER)]} metrics settle"
    assert phrase in section(read(README).text)
