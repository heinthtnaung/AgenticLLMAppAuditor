"""The development guide marks no run and prints none of this tool's output, and is held to that.

`docs/DEVELOPMENT.md` is the tests and how to work on the code; its table of
gated tests is held in `test_development_gated.py`. No live test reads this
page, so a `doc-check` marker added to it would be read by nothing, and a report
pasted under an `audit` command would be checked by nobody. Both are refused
here, where the plain suite sees them.
"""

import pytest

from doc_markers import unmarked_note
from doc_pages import DEVELOPMENT, read
from doc_runs import printed_runs
from doc_tool_output import unmarked_tool_output
from docs_samples import AUDIT_COMMAND, MARKED_OUTPUT, UNMARKED_OUTPUT, page_with

WRONG_COUNT = "expects"


def test_the_development_guide_marks_no_run():
    assert printed_runs(read(DEVELOPMENT)) == ()


def test_a_run_marked_on_the_development_guide_is_refused():
    # No live test reads this page, so a marked run here would be checked by nothing.
    with pytest.raises(ValueError, match=WRONG_COUNT):
        printed_runs(page_with(read(DEVELOPMENT), MARKED_OUTPUT))


def test_the_development_guide_leaves_no_output_of_this_tool_unmarked():
    page = read(DEVELOPMENT)
    assert len(unmarked_tool_output(page)) == DEVELOPMENT.unmarked_tool_output, unmarked_note(page)


def test_an_output_pasted_under_an_audit_command_on_the_development_guide_is_seen():
    page = page_with(read(DEVELOPMENT), f"{AUDIT_COMMAND}\n\n{UNMARKED_OUTPUT}")
    assert len(unmarked_tool_output(page)) == DEVELOPMENT.unmarked_tool_output + 1
