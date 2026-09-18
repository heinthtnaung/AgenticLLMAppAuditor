"""Where a run's files stand: three words, and each one has to be the true one.

`HistoryGroup.jsx`'s `files()` turns two booleans into the last column of every
history row. It is four lines and it is the most consequential text on the page,
because it is the only place a reader is told whether the evidence behind a
finding is still the evidence that run produced:

| It says | It means |
|---|---|
| `gone` | `artifacts_present` is false -- the directory has been cleaned |
| `on disk` | the files are there **and they are this run's** |
| `overwritten` | a later run of the same app wrote over them |

**The third is the one that matters, and it can be made to lie in one
character.** Swapping the ternary --

    return run.artifacts_current ? "overwritten" : "on disk";

-- makes a superseded run report **"on disk"**, and that was measured with the
whole suite green: 5117 passed. None of the three words appeared anywhere under
`tests/`. `docs/TODO.md`'s known-defect row about supersession is about exactly
this column: artifacts are keyed on the app name, not the run, so two audits of
one URL share `artifacts/<system>/<app>/`, and an older run's files are simply
not recoverable. Reporting that honestly is the whole mitigation; a column that
says "on disk" instead retracts it.

The text is older than this change, but this change lifted it into a new
`files()` in a new module -- so it is this change that owes it a test, and the
words are named here rather than left to a reader's eye.

**Each word is joined to the condition that produces it**, because all three
appear in the same four lines and a check for the strings alone passes on any
permutation of them. `test_run_artifacts_flags.py` holds where the two booleans
come from and what they mean on the wire; this is the only place their rendering
is named.

No test in this suite renders React -- a recorded defect -- so this reads the
function as text. It shows the branches are *written* that way round.

Reads one component as text. No fastapi, no node, no build.
"""

import re

from .jsx_sweep import FRONTEND_SRC, strip_comments

GROUP = FRONTEND_SRC / "components" / "HistoryGroup.jsx"

# The three words, and the one field each is a claim about. Named so a failure
# reads as "the column can lie" rather than as a regex that stopped matching.
GONE = "gone"
ON_DISK = "on disk"
OVERWRITTEN = "overwritten"

# Absent files are reported first and unconditionally: with no directory there
# is nothing for the second question to be about.
THE_ABSENT_BRANCH = re.compile(r'if \(!run\.artifacts_present\) return "gone";')

# And then the one that can lie. Joined to `artifacts_current` in the order the
# branches have to be in: **current** means the files are this run's, so it is
# `on disk`; not current means a later run wrote over them.
THE_SUPERSESSION_BRANCH = re.compile(
    r'return run\.artifacts_current \? "on disk" : "overwritten";')

# The swap, as the plant. This is the page 5117 passing tests were measured
# against, and a reader of it would take a superseded run's files for its own.
THE_BRANCHES_SWAPPED = 'return run.artifacts_current ? "overwritten" : "on disk";'

# The column has to reach a row as well as exist as a function.
THE_COLUMN = "<td className=\"nowrap\">{files(run)}</td>"

# A floor, so a file this test failed to read cannot satisfy the checks above.
MINIMUM_ELEMENTS = 8


def group() -> str:
    """The group header's own source, comments stripped: `files()` lives beside `Row`."""
    return strip_comments(GROUP.read_text(encoding="utf-8"))


# --- each word is the true one --------------------------------------------------

def test_files_that_are_not_there_are_reported_gone() -> None:
    """Checked first: with no directory the second question has nothing to be about."""
    assert THE_ABSENT_BRANCH.search(group())


def test_a_runs_own_files_read_on_disk_and_a_superseded_runs_read_overwritten() -> None:
    """The one that can lie, and the branch order is the whole claim."""
    assert THE_SUPERSESSION_BRANCH.search(group())


def test_the_two_branches_the_wrong_way_round_are_not_accepted() -> None:
    """Planted: this exact swap passed 5117 tests, and it retracts the honesty of the column."""
    assert THE_SUPERSESSION_BRANCH.search(THE_BRANCHES_SWAPPED) is None


def test_all_three_words_are_written_somewhere_in_the_function() -> None:
    """Non-vacuity, spelled as the words rather than as a count: a failure names which is missing."""
    missing = [word for word in (GONE, ON_DISK, OVERWRITTEN) if f'"{word}"' not in group()]
    assert missing == []


# --- and the column reaches a row -----------------------------------------------

def test_the_column_is_rendered_on_every_row() -> None:
    """A `files()` nothing calls is a correct function nobody reads: the fifth relation."""
    assert THE_COLUMN in group()


def test_the_sweep_read_a_component_and_not_an_empty_file() -> None:
    """Non-vacuity: an unreadable component satisfies the one absence check above."""
    assert len(re.findall(r"<[A-Za-z]", group())) >= MINIMUM_ELEMENTS
