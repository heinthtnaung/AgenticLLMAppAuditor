"""The README's stated Python minimum, pinned to pyproject and to what the suite is tested with.

The minimum stayed at 3.10 though only 3.11 was ever tested, because nothing held
the README's "Minimum" cell to pyproject's `requires-python` or to the "Tested
with" version in the same row. This keeps the three equal, so a revert of any one
of them -- including a minimum left behind the version actually tested -- turns
red instead of passing in silence.
"""

import pytest

from doc_pages import README, read, rewritten
from doc_prerequisites import major_minor, python_row, required_python

# The message python_row raises when a table carries no Python row to read.
NO_PYTHON_ROW = r"no '\| Python \|"


def test_the_readme_minimum_equals_pyproject_and_the_tested_with_version():
    tested_with, minimum = python_row(read(README))
    assert minimum == required_python() == major_minor(tested_with)


def test_a_readme_with_no_python_row_is_refused():
    page = read(README)
    without_row = "\n".join(line for line in page.text.splitlines() if "| Python |" not in line)
    with pytest.raises(ValueError, match=NO_PYTHON_ROW):
        python_row(rewritten(page, without_row))
