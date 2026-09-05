"""The registered-name denominators the write-up quotes, pinned to literals.

Split out of `test_vocabulary.py`, which owns the counting *rule* -- what is
registered, what is excluded, and how a scan is credited. This file owns only
the numbers that rule produces, because they are quoted in prose in two tracked
documents and prose does not fail.

Every number here is counted from live source at test time. None is a corpus
measurement: the corpus is gone, so the exercised numerators went with it and
only the denominators remain.
"""

from evaluation.vocabulary import registered_names
from parsing.languages import JAVASCRIPT, PYTHON

# --- The denominators the write-up quotes ----------------------------------
# Counted from the detector name tables, and quoted in prose in two tracked documents.
# They are pinned here because prose does not fail: Task 2 added four Python
# names and the "12 of 76" that stood in docs/TODO.md silently became wrong,
# with nothing to notice it. It has caught two drifts since: the MCP and dataset
# names added for the AIBOM's two new kinds moved Python 80 -> 86, and a
# hard-coded `datasets.load_dataset` briefly moved it to 87 -- one published API
# name counted as two, which is what made that entry the wrong fix.
# The exercised numerators (12 and 4) are not pinned and cannot be: the corpus
# that reached those names went on 2026-09-04, so they are a dated measurement,
# while the denominators are live source.
PYTHON_REGISTERED = 86
JAVASCRIPT_REGISTERED = 42
# The convention both documents use: the two languages *summed*, so a name both
# tables hold counts twice. The set union is smaller -- see the test below --
# and it is not the number in the prose.
CARRIED_TOTAL = 128

# The same two tables read as a set union: a name both languages register is one
# name, not two. Pinned to its own literal, because comparing the union to the
# sum is inclusion-exclusion and holds for every pair of sets.
DISTINCT_TOTAL = 107
REGISTERED_IN_BOTH = 21

STALE_NUMBER_MESSAGE = (
    "the registered-name count changed. That is fine, but it is quoted in prose: "
    "update docs/TODO.md (the vocabulary-coverage task, \"Python exercises 12 of "
    "86 registered names, JavaScript 4 of 42 -- so 112 of 128 are carried "
    "untested\") and docs/REPORT.md (\"the corpus exercised 16 of 128 carried "
    "names\") in the same change, then update this test."
)

DISTINCT_TOTAL_MESSAGE = (
    "the overlap between the two languages' tables moved, so the gap between the "
    "summed reading and the distinct one is no longer the one this test states. "
    "No document quotes these two, so update them here."
)


def test_the_python_registered_total_is_the_one_the_write_up_quotes() -> None:
    """The Python denominator, pinned so a table edit cannot leave the prose stale."""
    assert len(registered_names(PYTHON)) == PYTHON_REGISTERED, STALE_NUMBER_MESSAGE


def test_the_javascript_registered_total_is_the_one_the_write_up_quotes() -> None:
    """The JavaScript denominator, pinned for the same reason and read separately."""
    assert len(registered_names(JAVASCRIPT)) == JAVASCRIPT_REGISTERED, STALE_NUMBER_MESSAGE


def test_the_carried_total_is_the_two_languages_added_up() -> None:
    """"128 carried names" is the sum of the two tables, which is what the documents mean."""
    assert PYTHON_REGISTERED + JAVASCRIPT_REGISTERED == CARRIED_TOTAL
    assert len(registered_names(PYTHON)) + len(registered_names(JAVASCRIPT)) == CARRIED_TOTAL, \
        STALE_NUMBER_MESSAGE


def test_the_carried_total_counts_a_two_language_name_twice() -> None:
    """Sum, not union: `ChatOpenAI` is registered in both languages and counted in both.

    Both readings are pinned to their own literal, so the distance between them
    is asserted rather than described: 128 carried names against 107 distinct
    ones, because 21 are registered in both languages. Asserting the union
    against the sum instead would prove nothing -- `len(A | B)` equals
    `len(A) + len(B) - len(A & B)` for every pair of sets there is.
    """
    python_names, javascript_names = registered_names(PYTHON), registered_names(JAVASCRIPT)
    assert "ChatOpenAI" in python_names & javascript_names
    assert len(python_names & javascript_names) == REGISTERED_IN_BOTH, DISTINCT_TOTAL_MESSAGE
    assert len(python_names | javascript_names) == DISTINCT_TOTAL, DISTINCT_TOTAL_MESSAGE
