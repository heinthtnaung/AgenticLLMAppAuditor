"""The forget control is dead while a delete is in flight, and live again afterwards.

Split from `test_jsx_history_group.py`, which holds which runs the control is
offered for and what it asks before firing. This is the in-flight guard, and it
needed a file because it has **three ends** and only two of them are attributes.

A second click re-sends every id. The second round answers 404 on the rows the
first round removed, and the page reports "0 of 3 forgotten, 3 refused" about
three runs that really were forgotten -- a false alarm the page authors about
itself, which is the shape of failure this whole tool exists to expose, one
control deep.

**Two attributes cannot show when the flag is up, and that was measured.**
`disabled={forgetting}` on the header and `forgetting={forgetting === group.key}`
on the table are both still present on a `HistoryTable.forget` rewritten to
raise the flag *after* the round --

    await onForget(failed);
    setForgetting(group.key);
    setForgetting(null);

-- a page where the control is never disabled during a delete, with every
assertion in `test_jsx_history_group.py` and `test_jsx_history_fold.py` green.
So the third end is the round itself: the raise bracketed to the call and to the
clearing.

**The `finally` is inside the match on purpose.** Without it a rejected round
leaves that group disabled for ever, with nothing on the page able to clear it
-- the opposite failure, and just as silent.

**And the control has to say which state it is in.** Both labels exist whichever
way round the ternary is written, so swapping them -- idle reading
"Forgetting…", an in-flight round reading "Forget 3 failed" -- passes any check
that looks for the two strings. The condition is asserted with them.

No test in this suite renders React -- a recorded defect -- so this is the
source read as text. It can show the flag is *raised* around the call; it cannot
show a button greying out.

Reads two components as text. No fastapi, no node, no build.
"""

import re

from .jsx_sweep import FRONTEND_SRC, strip_comments

GROUP = FRONTEND_SRC / "components" / "HistoryGroup.jsx"
TABLE = FRONTEND_SRC / "components" / "HistoryTable.jsx"

# The three ends. The first two are attributes; the third is the only one that
# can say *when* the flag is up.
THE_BUSY_PROP = "disabled={forgetting}"
THE_BUSY_SOURCE = "forgetting={forgetting === group.key}"
THE_BUSY_ROUND = re.compile(
    r"setForgetting\(group\.key\);\s*try \{\s*await onForget\(failed\);\s*"
    r"\} finally \{\s*setForgetting\(null\);")

# What the control says in each state, as one expression. Both labels exist
# whichever way round they are written, so a swap -- idle reading "Forgetting…"
# and an in-flight round reading "Forget 3 failed" -- passes any check that
# looks for the two strings. The condition is what tells them apart.
THE_LABELS = ('{forgetting ? "Forgetting…" : `Forget ${failed.length} failed`}')

# The same two labels the wrong way round, as the plant.
THE_LABELS_SWAPPED = ('{forgetting ? `Forget ${failed.length} failed` : "Forgetting…"}')

# The two rewrites it refuses. The first raises the flag after the round, so the
# control is live for exactly as long as it matters; the second drops the
# `finally`, so a rejected round leaves the group disabled for ever.
A_FLAG_RAISED_AFTER_THE_ROUND = (
    "  async function forget(group, failed) {\n"
    "    await onForget(failed);\n"
    "    setForgetting(group.key);\n"
    "    setForgetting(null);\n  }\n")
A_ROUND_WITH_NO_FINALLY = (
    "  async function forget(group, failed) {\n"
    "    setForgetting(group.key);\n"
    "    await onForget(failed);\n"
    "    setForgetting(null);\n  }\n")


def group() -> str:
    """The group header's own source, comments stripped."""
    return strip_comments(GROUP.read_text(encoding="utf-8"))


def table() -> str:
    """The table's own source, comments stripped: it owns the flag and the round."""
    return strip_comments(TABLE.read_text(encoding="utf-8"))


# --- and a second click does not re-send the first round -----------------------

def test_the_control_is_disabled_while_a_delete_is_in_flight() -> None:
    """The second round 404s on rows the first removed, and reports them as refusals."""
    assert THE_BUSY_PROP in group()


def test_the_table_says_which_group_is_being_forgotten() -> None:
    """The second end: a prop nobody sets is `undefined`, and `disabled={undefined}` disables nothing."""
    assert THE_BUSY_SOURCE in table()


def test_the_flag_is_raised_before_the_round_and_cleared_after_it() -> None:
    """The third end, which no attribute can show: *when* the flag is up.

    Both attributes survive a `forget` that raises the flag after the round --
    measured -- so a page where the control is never disabled during a delete
    passed this file entirely. The `finally` is inside the match because a
    rejected round must clear the flag too.
    """
    assert THE_BUSY_ROUND.search(table())


def test_a_flag_raised_after_the_round_is_not_accepted() -> None:
    """Planted: the exact rewrite both attribute checks passed on."""
    assert THE_BUSY_ROUND.search(A_FLAG_RAISED_AFTER_THE_ROUND) is None


def test_a_round_that_cannot_fail_safely_is_not_accepted() -> None:
    """Planted: no `finally`, so one rejection disables that group until the page reloads."""
    assert THE_BUSY_ROUND.search(A_ROUND_WITH_NO_FINALLY) is None


def test_the_control_says_which_state_it_is_in() -> None:
    """A swap reads "Forgetting…" when idle and invites a second click when it is working."""
    assert THE_LABELS in group()


def test_the_two_labels_the_wrong_way_round_are_not_accepted() -> None:
    """Planted: both strings are present either way, so only the condition carries the claim."""
    assert THE_LABELS not in THE_LABELS_SWAPPED


def test_the_sweep_read_two_components_and_not_two_empty_files() -> None:
    """Non-vacuity: two unreadable components satisfy nothing above, but say so plainly."""
    assert len(group()) > 0 and len(table()) > 0
    assert "HistoryGroup" in table()
