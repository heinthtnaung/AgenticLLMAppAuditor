"""What the audit page passes the run overlay is what the run overlay reads.

A prop passed that the component does not destructure, and a prop destructured
that nobody passes, are both `undefined`, and React renders `undefined` as
nothing at all: no throw, no warning, an empty place on the page. That is the
same silent boundary `test_jsx_record_fields.py` exists for -- a record field
the page reads and no record carries -- one level up, between two components
this project owns on both sides.

It is asserted **in both directions** because the overlay's redesign moved both
ways at once. `onClose` went, when the panel stopped being dismissable, and
`error` arrived, when the poll error moved off the page body and into the card.
Either could have been left half done, and the half that fails is invisible:
a prop the card still takes apart but nobody passes renders as nothing, and a
prop the page still passes but the card no longer reads is dead markup on the
page's side.

**No test in this suite renders React**, a recorded defect this does not close.
Both lists are read out of the source as text, which is why the sweep is floored
and a mismatch is planted below: a regex that matched neither element would
compare two empty sets and pass. What text cannot see is a prop reached through
a spread (`{...props}`) or renamed while destructured -- neither is how these
two components are written today.

Reads two components as text. No fastapi, no node, no build.
"""

import re

from .jsx_sweep import FRONTEND_SRC, strip_comments

PAGE = FRONTEND_SRC / "pages" / "AuditPage.jsx"
OVERLAY = FRONTEND_SRC / "components" / "RunOverlay.jsx"

THE_OVERLAY = "RunOverlay"

# The props one element is handed, and the props a component takes apart. Both
# are read off the source, so neither list is transcribed here. `.*?` rather
# than "anything but a closing angle bracket", because a handler prop can carry
# an arrow and so a `>` inside the element -- `HistoryTable.jsx` passes
# `onForget={(failed) => forget(group, failed)}`. This element passes no such
# prop today, which is why the lazy form is about what may be added rather than
# what is there.
PROPS_PASSED = re.compile(rf"<{THE_OVERLAY}\b(.*?)/>", re.DOTALL)
PROP_NAME = re.compile(r"(\w+)=\{")
PROPS_TAKEN = re.compile(rf"function {THE_OVERLAY}\(\{{([^}}]*)\}}\)")

# A floor, so a sweep that read neither side cannot pass as a sweep that found
# no mismatch. Three props today, which is the floor exactly: the fourth went
# with the exit control on 2026-09-18, so this cannot be lowered any further
# without ceasing to be a floor.
MINIMUM_PROPS = 3

# Planted below, because the comparisons are empty sets either way. This is the
# prop the redesign dropped.
A_PROP_NOBODY_READS = "onClose"


def page() -> str:
    """The audit page's own source, comments stripped: they name props in prose."""
    return strip_comments(PAGE.read_text(encoding="utf-8"))


def props_passed() -> set[str]:
    """Every prop the page hands the overlay."""
    found = PROPS_PASSED.search(page())
    assert found, f"{PAGE.name} does not render <{THE_OVERLAY} ... /> as one element"
    return set(PROP_NAME.findall(found.group(1)))


def props_taken() -> set[str]:
    """Every prop the overlay takes apart, read off the component itself."""
    found = PROPS_TAKEN.search(strip_comments(OVERLAY.read_text(encoding="utf-8")))
    assert found, f"{OVERLAY.name} no longer destructures its props on one line"
    return {name.strip() for name in found.group(1).split(",") if name.strip()}


# --- the two lists are one list -----------------------------------------------

def test_every_prop_the_page_passes_is_one_the_overlay_takes_apart() -> None:
    """A prop the component does not destructure is `undefined`, and renders as nothing."""
    assert sorted(props_passed() - props_taken()) == []


def test_every_prop_the_overlay_takes_apart_is_one_the_page_passes() -> None:
    """The other direction: `onClose` survived the redesign in neither list."""
    assert sorted(props_taken() - props_passed()) == []


# --- and both lists were really read ------------------------------------------

def test_the_prop_sweep_read_both_sides() -> None:
    """Non-vacuity: two empty sets satisfy both comparisons above having read nothing."""
    assert len(props_passed()) >= MINIMUM_PROPS
    assert len(props_taken()) >= MINIMUM_PROPS


def test_a_prop_one_side_does_not_know_about_is_reported() -> None:
    """Planted: both comparisons above are empty sets either way."""
    planted = props_passed() | {A_PROP_NOBODY_READS}
    assert sorted(planted - props_taken()) == [A_PROP_NOBODY_READS]
