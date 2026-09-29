"""The usage guide's markers held to its own counts, which no other page's can make up for.

The guard's battery of damage runs once, on the README, in
`test_readme_markers.py`; the guard is the same on every page. What differs is
the counts, so these hold `docs/USAGE.md` to the ones `doc_pages` gives it. Like
the rest of `tests/docs`, they test the guard and not the page: green here says
the guide's markers are intact, not that the output they print reproduces.
"""

import pytest

from cli.arguments import Options

from doc_answers import answer_file
from doc_markers import RUN_DIRECTIVE, unmarked_note
from doc_pages import USAGE, read
from doc_runs import printed_runs
from doc_tool_output import unmarked_tool_output
from docs_samples import marker_lines, without_line

WRONG_COUNT = "expects"


def test_the_usage_guide_as_it_stands_parses_cleanly():
    """The precondition the usage guide's other checks rest on."""
    page = read(USAGE)
    assert len(printed_runs(page)) == USAGE.run_blocks
    assert answer_file(page)


def test_deleting_the_usage_guides_run_marker_is_refused():
    """The guide's count is its own, so a marker lost from it is not hidden by the README's."""
    page = read(USAGE)
    for line in marker_lines(page, RUN_DIRECTIVE):
        with pytest.raises(ValueError, match=WRONG_COUNT):
            printed_runs(without_line(page, line))


def test_the_council_progress_is_the_one_output_of_this_tool_the_guide_leaves_unmarked():
    """The one unchecked output fence, pinned so that no second one can join it unnoticed."""
    # RED HERE MEANS THE SET OF UNCHECKED OUTPUT CHANGED. The council's progress
    # is a council run's stderr and needs Ollama, so no marker reruns it. If it
    # now carries one, `doc_pages` and this test both need rewriting for the
    # page as it is. If another fence of this tool's output turned up with no
    # marker, the fix is a marker on it, not a raised count in `doc_pages`.
    page = read(USAGE)
    unmarked = unmarked_tool_output(page)
    assert len(unmarked) == USAGE.unmarked_tool_output, unmarked_note(page)
    assert all(is_a_council_run(runs) for runs in unmarked), "it follows no council run"


def is_a_council_run(runs: tuple[Options, ...]) -> bool:
    """Say whether any command in one shell fence names council members."""
    return any(run.council_models for run in runs)
