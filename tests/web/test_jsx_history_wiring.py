"""A click on the forget control reaches the round that deletes runs, and each group can open.

**This file exists because of a whole class of defect the rest of them cannot
see.** Four other files pin the delete: `test_jsx_delete_round.py` the loop,
`test_jsx_forget_report.py` what the page says, `test_jsx_forget_busy.py` the
in-flight flag, `test_jsx_history_group.py` the control and its confirmation.
Every one reads the *internals* of a function or an element. **None of them said
a click could get there**, and the measurement is stark: with
`onForget` dropped from `<HistoryTable runs={held.runs} />`, the whole suite --
5096 tests -- stayed green while every group's button called an `undefined`. The
feature was unreachable and nothing anywhere noticed.

The same hole sat one level down: `<HistoryGroup>`'s own `onForget` prop could go
and `test_jsx_forget_busy.py` would carry on pinning `forgetting={forgetting ===
group.key}` **on that very element**, with `THE_BUSY_ROUND` pinning the round it
can no longer reach. The round pinned, the flag pinned, the wire between them
not.

**Why no assertion-level sweep finds this.** Reading every presence check and
asking "is presence the claim?" can only find guards that are too *weak*. This
is a relationship with **no assertion at all** -- nothing to interrogate. It
takes the complementary sweep: enumerate every prop each changed component
passes or receives, and ask which are pinned. `docs/TODO.md` now carries that as
a fifth relation, **this reached from that**.

So this file is the chain, end to end, one wire per test:

- `HistoryPage` hands `forget` to the table.
- the table hands each group a `onForget` closed over that group.
- the table hands each group the toggle that opens it -- a `() => {}` there and
  no group can ever be opened, which is the whole list unreachable rather than
  one button.
- the table hands each group **the group**, and the header hands each row **the
  run**. Both were found by running that prop sweep over this change's own
  components after the two above were fixed, and both were measured MISSED: with
  `group={group}` gone every header renders `undefined.key` and `undefined.runs`,
  and with `run={run}` gone every row renders eight empty cells. A page of blank
  rows, and 1647 web tests green.

**`key=` is deliberately not in that list.** It is React's own reconciliation
hint, not a wire carrying data to a child, and pinning it would be a check
stricter than the claim.

What it cannot show: that React calls any of them. No test in this suite renders
React -- a recorded defect. What it *can* show is that both ends of each wire
name the same thing, which is what was missing.

Reads two components and one page as text. No fastapi, no node, no build.
"""

from .jsx_sweep import FRONTEND_SRC, strip_comments

PAGE = FRONTEND_SRC / "pages" / "HistoryPage.jsx"
TABLE = FRONTEND_SRC / "components" / "HistoryTable.jsx"
GROUP = FRONTEND_SRC / "components" / "HistoryGroup.jsx"

# The page's own element, whole. Written out rather than searched for by prop
# name, because the element without the prop is valid JSX and renders a table
# whose every button calls `undefined`.
# Both data props and both handler props, written as the source writes them but
# without the closing `/>`: the element gained `picked` and `onPick` on
# 2026-09-18 and spans two lines now, so matching to the close would pin the
# line break rather than the wiring.
THE_TABLE_ELEMENT = "<HistoryTable runs={held.runs} onForget={forget}"

# The two props the select boxes ride on, checked beside the element above so a
# table rendered without them is a column of checkboxes that record nothing.
THE_PICK_PROPS = ("picked={picked}", "onPick={pick}")

# The same element with the wire cut, as the plant: this is what 5096 green
# tests were measured against.
A_TABLE_WITH_NO_HANDLER = "      <HistoryTable runs={held.runs} />\n"

# What the table hands each group: the round, closed over the group it is for.
# `forget(group, failed)` and not `forget(failed)` -- the group is what names the
# busy flag, so a closure that dropped it would disable nothing.
THE_GROUP_HANDLER = "onForget={(failed) => forget(group, failed)}"

# The two data wires, as written. Without the first every header renders
# `undefined.key` and `undefined.runs`; without the second every row renders
# eight empty cells. Both measured green across the whole web suite before this.
THE_GROUP_DATA = "group={group}"
THE_GROUP_OPEN = "open={open.isOpen(group.key)}"
THE_ROW_DATA = "<Row key={run.run_id} run={run}"

# And the toggle that opens one. `() => {}` here leaves every group shut for
# ever, which hides every run rather than one control.
THE_GROUP_TOGGLE = "onToggle={() => open.toggle(group.key)}"

# The far end of the first wire: the prop the table takes apart, and the round it
# names. Both read, so a rename on either side is a failure here rather than a
# silently undefined call.
THE_TABLE_PROPS = "function HistoryTable({ runs, onForget, picked, onPick })"
THE_ROUND = "async function forget(group, failed)"

# The far end of the second: the prop the header takes apart, and the click that
# calls it.
THE_GROUP_PROPS = "onForget"
THE_CLICK = "onClick={() => confirmed(failed) && onForget(failed)}"


def page() -> str:
    """The history page's own source, comments stripped."""
    return strip_comments(PAGE.read_text(encoding="utf-8"))


def table() -> str:
    """The table's own source, comments stripped."""
    return strip_comments(TABLE.read_text(encoding="utf-8"))


def group() -> str:
    """The group header's own source, comments stripped."""
    return strip_comments(GROUP.read_text(encoding="utf-8"))


# --- the page reaches the table -----------------------------------------------

def test_the_page_hands_its_round_to_the_table() -> None:
    """The measured hole: without this prop the feature is unreachable and the suite is green."""
    assert THE_TABLE_ELEMENT in page()


def test_the_page_hands_the_table_both_halves_of_the_selection() -> None:
    """A checkbox column wired to neither prop records nothing and disables nothing."""
    for prop in THE_PICK_PROPS:
        assert prop in page(), prop


def test_a_table_element_with_no_handler_is_not_accepted() -> None:
    """Planted: this is the exact page 5096 passing tests were measured against."""
    assert THE_TABLE_ELEMENT not in A_TABLE_WITH_NO_HANDLER


def test_the_table_takes_that_prop_apart_and_names_the_round() -> None:
    """Both ends of one wire: a prop nobody destructures is `undefined`, silently."""
    assert THE_TABLE_PROPS in table()
    assert THE_ROUND in table()


# --- and the table reaches each group ------------------------------------------

def test_the_table_hands_each_group_a_round_closed_over_that_group() -> None:
    """`forget(group, failed)`: the group is what names the busy flag, so it may not be dropped."""
    assert THE_GROUP_HANDLER in table()


def test_the_group_header_takes_that_prop_apart_and_calls_it_on_a_click() -> None:
    """The far end: the control's `onClick` is the only thing that reaches the round."""
    assert THE_GROUP_PROPS in group()
    assert THE_CLICK in group()


def test_the_table_hands_each_group_the_group() -> None:
    """Measured MISSED: without it every header reads `undefined.key`, and 1647 tests pass."""
    assert THE_GROUP_DATA in table()


def test_the_table_tells_each_group_whether_it_is_open() -> None:
    """The hook's answer, per group: `aria-expanded={undefined}` and a table that never renders."""
    assert THE_GROUP_OPEN in table()


def test_the_header_hands_each_row_its_run() -> None:
    """Measured MISSED too: without it every row renders eight empty cells."""
    assert THE_ROW_DATA in group()


def test_the_table_hands_each_group_the_toggle_that_opens_it() -> None:
    """A `() => {}` here shuts every group for ever, which hides every run rather than one control."""
    assert THE_GROUP_TOGGLE in table()


def test_a_toggle_that_does_nothing_is_not_accepted() -> None:
    """Planted: the prop is present either way, and the name says nothing about the body."""
    assert THE_GROUP_TOGGLE not in "                      onToggle={() => {}}\n"
