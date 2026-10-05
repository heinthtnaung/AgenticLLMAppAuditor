"""The setup guide's stated Python minimum, held to the same three-way agreement as the README.

`docs/SETUP.md` repeats the minimum with trailing prose naming `requires-python`,
so its Minimum cell is read as its leading `X.Y` token. The same pin as the
README's: neither page may state a minimum the project no longer tests or the
packaging no longer allows.
"""

import pytest

from doc_pages import SETUP, read
from doc_prerequisites import lower_bound, major_minor, python_row, required_python

# The message lower_bound raises on a requirement that is not a `>=X.Y` bound.
NOT_A_LOWER_BOUND = "not a '>=X.Y' lower bound"


def test_the_setup_minimum_equals_pyproject_and_the_tested_with_version():
    tested_with, minimum = python_row(read(SETUP))
    assert minimum == required_python() == major_minor(tested_with)


def test_a_requirement_that_is_not_a_lower_bound_is_refused():
    with pytest.raises(ValueError, match=NOT_A_LOWER_BOUND):
        lower_bound("~=3.11")
