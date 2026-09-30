"""What the marker guard catches, and the one thing it knowingly does not.

**These test the guard, not the page.** Green here says the markers on
`README.md` are intact and that damaging one is noticed. It says nothing at all
about whether the output those blocks print still reproduces -- that needs a
real scan and lives behind `DOCS_LIVE_SCAN` in `test_readme_live.py`. A green
marker battery is not a verified README.

The guard is the same on every page, so its battery runs once, here, on the page
a reader meets first; `test_usage_markers.py` holds the usage guide to its own
counts. They run in the ordinary suite because every one is page parsing: no
corpus, no scanners, no network. Evidence that a guard bites belongs somewhere
that outlives the session that wrote it, and it means marker damage is caught by
anyone running `pytest` rather than only by someone who asked for a scan.

**Every mutation is derived from the parsed page, never from a quoted string.**
A test that pastes in today's wording turns into a no-op the day the page is
reworded, and passes -- which is the failure this whole check exists to refuse,
committed inside the test written to prove it does not happen.
"""

import pytest

from doc_answers import answer_file
from doc_markers import ANSWERS_DIRECTIVE, MARKER_NAME, RUN_DIRECTIVE, unmarked_note
from doc_pages import README, Page, read, rewritten
from doc_runs import printed_runs
from doc_tool_output import unmarked_tool_output
from docs_samples import (
    AUDIT_COMMAND,
    MARKED_OUTPUT,
    OTHER_COMMAND,
    UNMARKED_OUTPUT,
    line_changed,
    marker_lines,
    page_with,
    without_line,
)

# A slip of the fingers, and the name every marker carried before the pages split.
MISNAMINGS = {"misspelt": "doc-checks", "the old name": "readme-check"}

CANNOT_READ = "cannot be read"
WRONG_COUNT = "expects"
NO_ANSWER_BLOCK = "blocks; this check needs"

PROSE_COMMENT = "<!-- a note about the docs, in prose -->"
UNMARKED_ANSWERS = '```json\n{"answers": {"EXP-1": "No"}}\n```'


def test_the_page_as_it_stands_parses_cleanly():
    """The precondition every mutation below rests on: a broken page would pass them all."""
    page = read(README)
    assert len(printed_runs(page)) == README.run_blocks
    assert answer_file(page)


def test_deleting_any_run_marker_is_refused():
    """A deleted marker takes its own block out of the check while every other block passes."""
    page = read(README)
    for line in marker_lines(page, RUN_DIRECTIVE):
        with pytest.raises(ValueError, match=WRONG_COUNT):
            printed_runs(without_line(page, line))


@pytest.mark.parametrize("misnamed", MISNAMINGS.values(), ids=MISNAMINGS)
def test_misnaming_any_marker_is_refused_and_the_line_is_named(misnamed):
    """A typo, or the old name, would drop its block in silence, so the comment is named."""
    page = read(README)
    for line in marker_lines(page, RUN_DIRECTIVE):
        with pytest.raises(ValueError, match=CANNOT_READ) as refusal:
            printed_runs(line_changed(page, line, MARKER_NAME, misnamed))
        assert f":{line}" in str(refusal.value)


def test_a_marker_detached_from_its_fence_by_a_blank_line_is_refused():
    """The marker has to sit directly above its fence, and a blank line is easy to leave behind."""
    page = read(README)
    for line in marker_lines(page, RUN_DIRECTIVE):
        with pytest.raises(ValueError, match=CANNOT_READ):
            printed_runs(detached(page, line))


def test_deleting_the_answers_marker_is_refused():
    """Without the answer file no documented command can run, so its absence cannot pass."""
    page = read(README)
    for line in marker_lines(page, ANSWERS_DIRECTIVE):
        with pytest.raises(ValueError, match=NO_ANSWER_BLOCK):
            answer_file(without_line(page, line))


def test_a_prose_comment_mentioning_the_docs_is_not_mistaken_for_a_marker():
    """A guard that fires on a legitimate edit gets switched off, so the net stays narrow."""
    assert len(printed_runs(page_with(read(README), PROSE_COMMENT))) == README.run_blocks


def test_a_second_unmarked_json_example_is_not_mistaken_for_the_answer_file():
    """The page may grow another JSON example, and only the marked one is the answer file."""
    page = page_with(read(README), UNMARKED_ANSWERS)
    assert answer_file(page)
    assert len(printed_runs(page)) == README.run_blocks


def test_a_marked_block_added_without_raising_the_count_is_refused():
    """The count fails both ways, so a new block cannot land quietly uncovered."""
    with pytest.raises(ValueError, match=WRONG_COUNT):
        printed_runs(page_with(read(README), MARKED_OUTPUT))


def test_a_block_pasted_with_no_marker_is_not_noticed_which_is_the_known_gap():
    """The gap `doc_markers` documents, asserted so that closing it cannot happen unremarked."""
    # RED HERE MEANS THE GAP HAS BEEN CLOSED, not that something broke. If you
    # have made this fail you have taught the check to see an unmarked block --
    # which is good -- and `doc_markers`'s docstring still says it cannot.
    # Correct that claim in the same commit and rewrite this as the test of the
    # new behaviour. Deleting it instead puts the page back to trusting nobody.
    page = page_with(read(README), f"{OTHER_COMMAND}\n\n{UNMARKED_OUTPUT}")
    assert len(printed_runs(page)) == README.run_blocks
    assert len(unmarked_tool_output(page)) == len(unmarked_tool_output(read(README)))


def test_the_readme_leaves_no_output_of_this_tool_unmarked():
    """Every fence of this tool's output on the README is one a live check reruns."""
    # RED HERE MEANS A FENCE OF THIS TOOL'S OUTPUT CARRIES NO MARKER. The fix is
    # a marker on it, or a language on a fence that is not output, not a count.
    page = read(README)
    assert len(unmarked_tool_output(page)) == README.unmarked_tool_output, unmarked_note(page)


def test_an_output_pasted_under_an_audit_command_is_seen_as_unmarked():
    """The guard above bites: a block pasted after this tool's command is counted."""
    page = page_with(read(README), f"{AUDIT_COMMAND}\n\n{UNMARKED_OUTPUT}")
    assert len(unmarked_tool_output(page)) == README.unmarked_tool_output + 1


def detached(page: Page, line_number: int) -> Page:
    """Give the page with a blank line pushed between one marker and its fence."""
    lines = page.text.splitlines(keepends=True)
    lines.insert(line_number, "\n")
    return rewritten(page, "".join(lines))
