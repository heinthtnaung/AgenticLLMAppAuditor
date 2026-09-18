"""The control that forgets runs: offered for failures only, counted, and asked about.

`HistoryGroup.jsx` heads one repository's runs and carries the one control on
this page that destroys anything. Four decisions hold it together, and each one
fails quietly.

**It is offered for failed runs and no others.** The server refuses every other
status with 409, so a control offered on a finished run produces a refusal a
reader did nothing to deserve -- and the count in the button ("Forget 3 failed")
would be a number that does not describe what the click does. The set is
`failedIn(group, FAILED)`, with `FAILED` imported from `runStatus.js`;
`test_jsx_run_status_vocabulary.py` is what keeps that from becoming the bare
string `"failed"` again, and this file holds that the control is gated on the
set at all.

**It asks first.** The endpoint has no authentication and a forgotten row cannot
be recovered, so the control goes through `window.confirm` -- which blocks,
cannot be mis-clicked past, and needs nothing this page does not already have.
The count is in the question, because "forget 1" and "forget 9" are different
decisions.

**Whether it is live while a delete is in flight is `test_jsx_forget_busy.py`**,
split out because that decision has three ends and two of them are attributes
that cannot say *when* the flag is raised.

**Every check here joins two things in one expression, and that is the lesson
rather than a style.** `failed.length > 0 &&` is written twice in this header
and `failed.length` five times, so an "is it present" check over this file
passes on a version with the gate or the count taken off the control. Two were
measured doing exactly that in this file's first draft, and a third -- the
in-flight guard, now next door -- one round later, under a paragraph already
claiming the decision "fails quietly". Each check names the gate *and* the thing
it guards, with the defect planted as a non-match.

The group's figure and its folding are `test_jsx_history_fold.py`: a different
claim about the same header, split out when this file passed the ~200-line rule.

No test in this suite renders React -- a recorded defect -- so all of this is
the source read as text. It can show a gate is *written*; it cannot show what a
click does. Comments are stripped first, so a header explaining a decision in
prose is not what satisfies the check for it.

Reads two components as text. No fastapi, no node, no build.
"""

import re

from .jsx_sweep import FRONTEND_SRC, strip_comments

GROUP = FRONTEND_SRC / "components" / "HistoryGroup.jsx"
TABLE = FRONTEND_SRC / "components" / "HistoryTable.jsx"

# The count in the header, beside the repository's name. Named for two reasons:
# a reader scanning the list needs it, and it is the **premise** that makes the
# regex below necessary -- it is the second `failed.length > 0 &&` in this file,
# and the reason a bare check for those words could not tell a gated control
# from an ungated one. Delete the tag and the regex silently becomes as strong
# as the substring it replaced.
THE_FAILED_TAG = re.compile(
    r'\{failed\.length > 0 && \(\s*<span className="tag tag--crit">'
    r"\{failed\.length\} failed</span>")

# The failed runs of one group, and where the word comes from. The binding, not
# the call: `failed` is the name the gate, the label and the handoff all read,
# so a `failedIn(...)` whose answer went somewhere else would leave three checks
# passing over a different list.
THE_FAILED_SET = "const failed = failedIn(group, FAILED);"
THE_VOCABULARY_IMPORT = re.compile(r'import \{([^}]*)\} from "[./]*runStatus\.js";')
THE_STATUS_NAME = "FAILED"

# What the control sits behind, and the element it has to sit immediately in
# front of. One expression rather than two substrings, because
# `failed.length > 0 &&` is written **twice** in this header -- once for the
# "N failed" tag and once for the control -- so a check that the words appear
# somewhere is satisfied by a control with no gate at all. Measured: this file's
# first draft passed with the button's gate replaced by `true &&`.
THE_GATED_CONTROL = re.compile(
    r"\{failed\.length > 0 && \(\s*<button[^>]*?group__forget")

# The gate taken off, as the plant for the regex above.
A_CONTROL_WITH_NO_GATE = '{true && (\n  <button className="filter group__forget"'

# What the control hands on, and the number it promises. A button that says
# "Forget 3 failed" and hands on a different list is a count that does not
# describe the click.
THE_HANDOFF = "onForget(failed)"
THE_CONTROL_LABEL = "`Forget ${failed.length} failed`"

# Asking first, and the one call that does it. The count is matched inside the
# question's own template literal: `failed.length` is written five times in this
# header, so a slice from the call to the end of the file finds one of the
# others and a countless dialog passes.
THE_CONFIRM = "window.confirm"
THE_COUNTED_QUESTION = re.compile(r"window\.confirm\(\s*`[^`]*\$\{failed\.length\}")
THE_CONFIRMED_HANDOFF = "confirmed(failed) && onForget(failed)"

# A dialog that asks and does not say how many, as the plant for the regex above.
A_COUNTLESS_DIALOG = (
    "  return window.confirm(\n"
    "    `Forget the failed runs? `\n"
    '    + "Their rows are deleted from the history and cannot be recovered.");\n')

# A floor, so a file this test failed to read cannot satisfy the checks above.
MINIMUM_ELEMENTS = 8


def group() -> str:
    """The group header's own source, comments stripped: its comments name the decisions in prose."""
    return strip_comments(GROUP.read_text(encoding="utf-8"))


def table() -> str:
    """The table's own source, comments stripped."""
    return strip_comments(TABLE.read_text(encoding="utf-8"))


def vocabulary_names() -> set[str]:
    """Every status constant the group header takes from the shared vocabulary."""
    found = THE_VOCABULARY_IMPORT.search(group())
    assert found, f"{GROUP.name} imports nothing from runStatus.js"
    return {name.strip() for name in found.group(1).split(",") if name.strip()}


# --- the delete is offered for failed runs only --------------------------------

def test_the_set_offered_for_deletion_is_the_failed_runs() -> None:
    """Every other status is a 409 from the server, so offering one is offering a refusal."""
    assert THE_FAILED_SET in group()


def test_the_header_says_how_many_of_a_groups_runs_failed() -> None:
    """A reader scans for this -- and it is the premise that makes the next check necessary."""
    assert THE_FAILED_TAG.search(group())


def test_the_status_it_selects_on_comes_from_the_shared_vocabulary() -> None:
    """Joined to `runStatus.js`, not a bare string: a rename in `src/` has to reach here."""
    assert THE_STATUS_NAME in vocabulary_names()


def test_the_control_is_rendered_only_when_something_failed() -> None:
    """A group with nothing to forget offers nothing, rather than a button that always refuses."""
    assert THE_GATED_CONTROL.search(group())


def test_a_control_with_the_gate_taken_off_is_not_accepted() -> None:
    """Planted: the same words appear twice in this file, so "present" is not "guarding"."""
    assert THE_GATED_CONTROL.search(A_CONTROL_WITH_NO_GATE) is None


def test_the_count_on_the_control_is_the_set_it_hands_on() -> None:
    """"Forget 3 failed" handing on a different list is a number that does not describe the click."""
    assert THE_CONTROL_LABEL in group()
    assert THE_HANDOFF in group()


# --- and it asks before it destroys anything -----------------------------------

def test_forgetting_goes_through_a_confirmation() -> None:
    """No authentication, and a forgotten row cannot be recovered."""
    assert THE_CONFIRM in group()


def test_the_confirmation_gates_the_handoff_rather_than_preceding_it() -> None:
    """Written as one expression: a confirm whose answer is discarded asks nothing."""
    assert THE_CONFIRMED_HANDOFF in group()


def test_the_question_names_how_many_runs_it_is_about() -> None:
    """"Forget 1" and "forget 9" are different decisions, and the dialog is where that is said."""
    assert THE_COUNTED_QUESTION.search(group())


def test_a_dialog_that_asks_without_saying_how_many_is_not_accepted() -> None:
    """Planted: `failed.length` appears five times here, so "somewhere after" finds another."""
    assert THE_COUNTED_QUESTION.search(A_COUNTLESS_DIALOG) is None


def test_the_sweep_read_two_components_and_not_two_empty_files() -> None:
    """Non-vacuity: an unreadable component satisfies every check above that is an absence."""
    assert len(re.findall(r"<[A-Za-z]", group())) >= MINIMUM_ELEMENTS
    assert len(re.findall(r"<[A-Za-z]", table())) >= 1
