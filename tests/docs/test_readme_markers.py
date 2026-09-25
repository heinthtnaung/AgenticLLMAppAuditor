"""What the marker guard catches, and the one thing it knowingly does not.

**These test the guard, not the page.** Green here says the markers on
`README.md` are intact and that damaging one is noticed. It says nothing at all
about whether the output those blocks print still reproduces -- that needs a
real scan and lives behind `README_LIVE_SCAN` in `test_readme_live.py`. A green
marker battery is not a verified README.

They run in the ordinary suite because every one is page parsing: no corpus, no
scanners, no network. Evidence that a guard bites belongs somewhere that
outlives the session that wrote it, which is the standard this project holds
everything else to, and it means marker damage is caught by anyone running
`pytest` rather than only by someone who asked for a scan.

**Every mutation is derived from the parsed page, never from a quoted string.**
A test that pastes in today's wording turns into a no-op the day the page is
reworded, and passes -- which is the failure this whole check exists to refuse,
committed inside the test written to prove it does not happen.
"""

import pytest

from readme_answers import answer_file
from readme_markers import (
    ANSWERS_DIRECTIVE,
    EXPECTED_RUN_BLOCKS,
    RUN_DIRECTIVE,
    found_blocks,
    read_readme,
)
from readme_runs import printed_runs
from readme_tool_output import unmarked_tool_output

MARKER_NAME = "readme-check"
MISSPELLING = "readme-checks"

CANNOT_READ = "cannot be read"
WRONG_COUNT = "expects"
NO_ANSWER_BLOCK = "blocks; this check needs"

PROSE_COMMENT = "<!-- a note about the readme, in prose -->"
UNMARKED_ANSWERS = '```json\n{"answers": {"EXP-1": "No"}}\n```'
UNMARKED_OUTPUT = (
    "```\n"
    "ORGANISATION RISK (18)  ·  the source changes the band on 99\n"
    "  CVE-2021-4279        ghsa 11.1 to nvd 22.2       Nonsense\n"
    "```"
)
MARKED_OUTPUT = f"<!-- {MARKER_NAME}: {RUN_DIRECTIVE} --answers -->\n{UNMARKED_OUTPUT}"


def test_the_page_as_it_stands_parses_cleanly():
    """The precondition every mutation below rests on: a broken page would pass them all."""
    page = read_readme()
    assert len(printed_runs(page)) == EXPECTED_RUN_BLOCKS
    assert answer_file(page)


def test_deleting_any_run_marker_is_refused():
    """A deleted marker takes its own block out of the check while every other block passes."""
    page = read_readme()
    for line in marker_lines(page, RUN_DIRECTIVE):
        with pytest.raises(ValueError, match=WRONG_COUNT):
            printed_runs(without_line(page, line))


def test_misspelling_any_marker_is_refused_and_the_line_is_named():
    """A typo would drop its block in silence, so the comment is named rather than skipped."""
    page = read_readme()
    for line in marker_lines(page, RUN_DIRECTIVE):
        with pytest.raises(ValueError, match=CANNOT_READ) as refusal:
            printed_runs(misspelt(page, line))
        assert f":{line}" in str(refusal.value)


def test_a_marker_detached_from_its_fence_by_a_blank_line_is_refused():
    """The marker has to sit directly above its fence, and a blank line is easy to leave behind."""
    page = read_readme()
    for line in marker_lines(page, RUN_DIRECTIVE):
        with pytest.raises(ValueError, match=CANNOT_READ):
            printed_runs(detached(page, line))


def test_deleting_the_answers_marker_is_refused():
    """Without the answer file no documented command can run, so its absence cannot pass."""
    page = read_readme()
    for line in marker_lines(page, ANSWERS_DIRECTIVE):
        with pytest.raises(ValueError, match=NO_ANSWER_BLOCK):
            answer_file(without_line(page, line))


def test_a_prose_comment_mentioning_the_readme_is_not_mistaken_for_a_marker():
    """A guard that fires on a legitimate edit gets switched off, so the net stays narrow."""
    assert len(printed_runs(page_with(read_readme(), PROSE_COMMENT))) == EXPECTED_RUN_BLOCKS


def test_a_second_unmarked_json_example_is_not_mistaken_for_the_answer_file():
    """The page may grow another JSON example, and only the marked one is the answer file."""
    page = page_with(read_readme(), UNMARKED_ANSWERS)
    assert answer_file(page)
    assert len(printed_runs(page)) == EXPECTED_RUN_BLOCKS


def test_a_marked_block_added_without_raising_the_count_is_refused():
    """The count fails both ways, so a new block cannot land quietly uncovered."""
    with pytest.raises(ValueError, match=WRONG_COUNT):
        printed_runs(page_with(read_readme(), MARKED_OUTPUT))


def test_a_block_pasted_with_no_marker_is_not_noticed_which_is_the_known_gap():
    """The gap `readme_markers` documents, asserted so that closing it cannot happen unremarked."""
    # RED HERE MEANS THE GAP HAS BEEN CLOSED, not that something broke. If you
    # have made this fail you have taught the check to see an unmarked block --
    # which is good -- and `readme_markers`'s docstring still says it cannot.
    # Correct that claim in the same commit and rewrite this as the test of the
    # new behaviour. Deleting it instead puts the page back to trusting nobody.
    page = page_with(read_readme(), UNMARKED_OUTPUT)
    assert len(printed_runs(page)) == EXPECTED_RUN_BLOCKS
    assert len(unmarked_tool_output(page)) == len(unmarked_tool_output(read_readme()))


def test_the_council_progress_is_the_one_output_of_this_tool_the_page_leaves_unmarked():
    """The one unchecked output fence, pinned so that no second one can join it unnoticed."""
    # RED HERE MEANS THE SET OF UNCHECKED OUTPUT CHANGED. The council's progress
    # is a council run's stderr and needs Ollama, so no marker reruns it. If it
    # now carries one, `readme_markers`'s docstring and this test both need
    # rewriting for the page as it is. If another fence of this tool's output
    # turned up with no marker, the fix is a marker on it, not a longer list here.
    unmarked = unmarked_tool_output(read_readme())
    assert len(unmarked) == 1, f"{len(unmarked)} unmarked fences of this tool's output"
    assert any(run.council_models for run in unmarked[0]), "it follows no council run"


def marker_lines(page: str, directive_word: str) -> list[int]:
    """Give the line each marker of one kind sits on, read off the page rather than quoted."""
    blocks = found_blocks(page)
    found = [line for directive, _, line in blocks if directive.split()[0] == directive_word]
    if found:
        return found
    raise ValueError(f"no '{directive_word}' marker on the page to damage, so nothing was tested")


def without_line(page: str, line_number: int) -> str:
    """Give the page with one line gone, as a deletion would leave it."""
    lines = page.splitlines(keepends=True)
    del lines[line_number - 1]
    return "".join(lines)


def misspelt(page: str, line_number: int) -> str:
    """Give the page with one marker's name mistyped, as a slip of the fingers would leave it."""
    lines = page.splitlines(keepends=True)
    changed = lines[line_number - 1].replace(MARKER_NAME, MISSPELLING)
    if changed == lines[line_number - 1]:
        raise ValueError(f"line {line_number} carries no '{MARKER_NAME}' to mistype")
    lines[line_number - 1] = changed
    return "".join(lines)


def detached(page: str, line_number: int) -> str:
    """Give the page with a blank line pushed between one marker and its fence."""
    lines = page.splitlines(keepends=True)
    lines.insert(line_number, "\n")
    return "".join(lines)


def page_with(page: str, addition: str) -> str:
    """Give the page with something appended, which is where a new block would be least noticed."""
    return f"{page}\n\n{addition}\n"
