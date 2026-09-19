"""A group says how many runs it is showing, and stays folded until asked.

Split from `test_jsx_history_group.py`, which holds the forget control. Same two
components, a different claim, and the split happened when the two together
passed the ~200-line rule.

**The figure says "shown", not "stored".** The list this page is handed is
capped at `HISTORY_LIST_LIMIT` newest-first, so a repository with ten runs
behind the cap heads a group of three. "3 stored" would be false, and falsely
precise: a reader would take it for the whole history of that repository and
conclude the other seven had been deleted. The stored/shown pair beside the page
heading is what makes the group figure readable at all, which is why
`test_jsx_page_heads.py` holds that the pair survived the prose being cut.

**The number and the word are checked as one fragment**, for the reason the
sibling file records in full: "shown" appearing somewhere in a component says
nothing about what any particular number is called, and two checks in that shape
were measured passing over the defect they name.

**An empty history says so, and says what can be forgotten.** `if (!runs.length)`
returns a sentence *instead of* the groups -- relation three, this-instead-of-
that -- and neither the gate nor its text was named anywhere, though the text was
**reworded by this change** to mention that a run is kept "until someone forgets
it". Turned to `if (false)`, an empty history renders an empty fragment: no
groups, no sentence, a blank card that reads as a page that failed to load. The
suite was green on it.

**The disclosure is announced.** `aria-expanded={open}` on the header button is
the only thing that tells a screen reader whether a group is open; without it a
folded control is silent about its own state. `aria-modal`, `aria-labelledby`
and `aria-label` are each pinned by an existing file in this folder, so the
convention exists and this attribute was simply outside it.

**Folded by default** is `useExpanded`'s own behaviour -- its state starts as an
empty set -- and `test_use_expanded.py` runs that hook under node and holds it.
What is asserted here is only that the table asks *that* hook rather than
growing a fourth copy of the same three behaviours, and that it groups through
`repoGroup.js` rather than keying rows itself. Both are checked as the lines
that **call** them: an identifier appears in an import, so a table that imported
either and then did the work itself would pass a check for the bare name.

**And a single repository is not offered "every repository".** The toggle-all
control is hidden when there is one group, whose own header already toggles
those rows. Every assertion that existed named the button -- `type`,
`className`, `onClick`, in the attribute register -- and none named its gate.

No test in this suite renders React -- a recorded defect -- so this is the
source read as text. Comments are stripped first, so a header explaining "shown"
in prose is not what satisfies the check for it.

Reads two components as text. No fastapi, no node, no build.
"""

import re

from .jsx_sweep import FRONTEND_SRC, strip_comments

GROUP = FRONTEND_SRC / "components" / "HistoryGroup.jsx"
TABLE = FRONTEND_SRC / "components" / "HistoryTable.jsx"

# The group figure and the word it is labelled with, joined into one fragment.
# `THE_DISHONEST_LABEL` is named as well, because the joined check alone would
# be satisfied by a second, differently labelled figure beside it.
THE_FIGURE = "group.runs.length"

# The word the figure carries. It was "shown" until 2026-09-18 and is "record"
# now, pluralised beside it. What the label has to do is unchanged and is the
# reason `THE_DISHONEST_LABEL` is still named: say what this number *is* without
# implying it is the whole history, so a reader looking at ten of fifty runs
# cannot conclude the other forty were deleted. The stored-against-shown
# difference is spelled out where it decides something -- `confirmedClear` says
# "Only N of them are shown here" before wiping the lot.
THE_LABELLED_FIGURE = f"{{{THE_FIGURE}}} record"
THE_DISHONEST_LABEL = "stored"

# The same figure under the wrong word, as the plant for the check above.
THE_FIGURE_MISLABELLED = f"{{{THE_FIGURE}}} stored"

# What an empty history shows instead of groups, and the gate that chooses it.
# Both named: the gate alone could return anything, and the sentence alone could
# be rendered beside a table that is also empty.
THE_EMPTY_GATE = "if (!runs.length) {"
THE_EMPTY_TEXT = "No audits yet. Every run started from this page is kept here until"
THE_EMPTY_CLASS = 'className="empty"'

# The gate defeated, as its plant: a blank card that reads as a failed load.
A_GATE_THAT_NEVER_FIRES = "  if (false) {\n"

# How the header announces whether its group is open. The only thing that tells
# a screen reader; the three sibling attributes are pinned by existing files, so
# this was a gap in a convention rather than a new idea.
THE_DISCLOSURE_STATE = "aria-expanded={open}"

# The shared open/closed hook and the grouping, written as the lines that *call*
# them rather than as the names. An identifier is present in an import, so a
# table that imported either and then keyed its rows itself would satisfy a
# check for the name while doing neither thing.
THE_HOOK = "const open = useExpanded(groups.map((group) => group.key));"
THE_OPEN_QUESTION = "open.isOpen(group.key)"
THE_GROUPING = "const groups = groupRuns(runs);"
THE_GROUPS_RENDERED = "groups.map((group) => ("

# An import and nothing else, as the plant for both.
IMPORTS_ALONE = (
    'import { groupRuns } from "../repoGroup.js";\n'
    'import { useExpanded } from "../useExpanded.js";\n')

# The gate joined to the control it hides, as one expression. The register pins
# that button's `type`, `className` and `onClick` and the gate's own words say
# nothing about what they guard, so only the join says *gated by*.
# `THE_TOGGLE_ALL` is that control with no gate at all, and it matches the plant
# below -- which is what makes the plant's non-match a demonstration rather than
# a comparison of two strings that share nothing.
THE_TOGGLE_ALL = re.compile(r"<button[^>]*?onClick=\{open\.toggleAll\}")
THE_GATED_TOGGLE_ALL = re.compile(
    r"\{groups\.length > 1 && \(\s*<button[^>]*?onClick=\{open\.toggleAll\}")

# The gate replaced by one that always fires, as the plant for the regex above.
A_TOGGLE_ALL_WITH_NO_GATE = '{true && (\n  <button type="button" onClick={open.toggleAll}>'

# A floor, so a file this test failed to read cannot satisfy the checks above.
MINIMUM_ELEMENTS = 8


def group() -> str:
    """The group header's own source, comments stripped: its comments explain "shown" in prose."""
    return strip_comments(GROUP.read_text(encoding="utf-8"))


def table() -> str:
    """The table's own source, comments stripped."""
    return strip_comments(TABLE.read_text(encoding="utf-8"))


# --- the group figure says what it is ------------------------------------------

def test_the_group_figure_is_the_runs_shown_and_is_labelled_so() -> None:
    """The list is capped, so a repository with ten runs behind the cap heads a group of three."""
    assert THE_LABELLED_FIGURE in group()


def test_the_group_figure_is_not_labelled_stored() -> None:
    """"Stored" is the store's own count, which this page is never handed per repository."""
    assert THE_DISHONEST_LABEL not in group()


def test_the_same_figure_under_the_wrong_word_is_not_accepted() -> None:
    """Planted: the number alone is right either way, so the word is what carries the claim."""
    assert THE_LABELLED_FIGURE not in THE_FIGURE_MISLABELLED


# --- an empty history says so -------------------------------------------------

def test_an_empty_history_renders_a_sentence_instead_of_groups() -> None:
    """Measured MISSED: `if (false)` leaves a blank card that reads as a failed load."""
    assert THE_EMPTY_GATE in table()
    assert THE_EMPTY_TEXT in table()
    assert THE_EMPTY_CLASS in table()


def test_a_gate_that_never_fires_is_not_accepted() -> None:
    """Planted: the sentence is still in the file, unreachable, and nothing else noticed."""
    assert THE_EMPTY_GATE not in A_GATE_THAT_NEVER_FIRES


# --- and the groups are folded by the hook the other tables use ----------------

def test_the_header_announces_whether_its_group_is_open() -> None:
    """Without it a folded control is silent to a screen reader about its own state."""
    assert THE_DISCLOSURE_STATE in group()



def test_the_table_groups_on_the_served_repository_key() -> None:
    """`repoGroup.js` joins on `canonical_repo_url`; this is the table asking it to, and rendering it."""
    assert THE_GROUPING in table()
    assert THE_GROUPS_RENDERED in table()


def test_the_table_folds_its_groups_with_the_shared_hook() -> None:
    """Closed by default is the hook's own behaviour, held under node in `test_use_expanded.py`."""
    assert THE_HOOK in table()
    assert THE_OPEN_QUESTION in table()


def test_the_toggle_all_control_is_rendered_only_when_there_is_a_second_group() -> None:
    """One group's own header toggles the same rows, so the control is not offered there."""
    assert THE_GATED_TOGGLE_ALL.search(table())


def test_a_toggle_all_with_the_gate_taken_off_is_not_accepted() -> None:
    """Planted: `true &&` keeps every attribute the register pins, and the suite stayed green."""
    assert THE_TOGGLE_ALL.search(A_TOGGLE_ALL_WITH_NO_GATE)
    assert THE_GATED_TOGGLE_ALL.search(A_TOGGLE_ALL_WITH_NO_GATE) is None


def test_importing_either_one_without_calling_it_is_not_accepted() -> None:
    """Planted: a bare identifier is present in an import, which is not a table that uses it."""
    assert THE_GROUPING not in IMPORTS_ALONE
    assert THE_HOOK not in IMPORTS_ALONE


def test_the_sweep_read_two_components_and_not_two_empty_files() -> None:
    """Non-vacuity: an unreadable component satisfies the one absence check above."""
    assert len(re.findall(r"<[A-Za-z]", group())) >= MINIMUM_ELEMENTS
    assert len(re.findall(r"<[A-Za-z]", table())) >= 1
