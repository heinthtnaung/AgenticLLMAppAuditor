"""The run overlay offers no control at all: no dismiss, and since 2026-09-18 no exit.

Split from `test_jsx_overlay_card.py`, which holds what the panel renders. This
is the one decision the panel makes about itself, and it is the reason the file
crossed the ~200-line rule -- a claim with two plants beside a claim with two
plants.

**It cannot be closed, and that is the honest position rather than an
oversight.** An audit cannot be cancelled -- the page has no endpoint for it and
`docs/TODO.md` records why -- so a dismiss would hide a run that carries on,
with the Audit button still disabled and nothing on screen saying why. That is
expressed by passing the modal no `onClose`, which is why
`test_modal_contract.py` asserts the pairing across both consumers and this file
asserts that the panel mentions no dismiss of its own.

**And it offers no exit either, which is a decision and not the absence of
one.** Until 2026-09-18 the claim was *exactly one* control -- a link to the
run's own page, so a reader would not be stranded under a scrim that covers the
nav bar. The user asked for it to go, so the surviving claim is the stronger
one, **zero controls**: a card with one button now fails here, where before a
card with none did. The cost is recorded in `docs/TODO.md`'s cancel row rather
than softened here.

Counting is still the form the claim takes, because the close control the modal
*may* render is not this panel's: the panel passes no `onClose`, so it gets
none, and `test_modal_contract.py` holds that pairing.

**Both absences are planted**, because `== []` is what a sweep that read nothing
returns too, and a button is not the only shape an exit takes.

Reads one component as text. No fastapi, no node, no build.
"""

import re

from .jsx_sweep import FRONTEND_SRC, strip_comments

OVERLAY = FRONTEND_SRC / "components" / "RunOverlay.jsx"

# A control, spelled once. The count is what carries the decision, and it is
# zero: see the docstring for what that replaced.
BUTTON = re.compile(r"<button\b")

# Every other way out this panel could be written, so "no control" is not read
# off the `<button>` spelling alone. `onOpenRun` is the prop the removed button
# called, `navigate` and `runPath` are what it would have called directly, and
# an anchor is a way out that is not a button at all.
NO_WAY_OUT = ("onOpenRun", "navigate", "runPath", "<a ")

# What a dismiss would be written as, on this panel's side: the prop it would
# have to pass the modal, and the state a dismiss would carry. Not a general ban
# on effects -- a focus trap is an effect a modal may well need -- and not a ban
# on the modal having a close control, only on this caller asking for one.
NO_WAY_TO_DISMISS = ("onClose", "onDismiss", "Escape", "useState(")

# A floor, so a file this test failed to read cannot satisfy the absences above.
MINIMUM_ELEMENTS = 5


def card() -> str:
    """The overlay's own source, comments stripped: its docstring names every decision."""
    return strip_comments(OVERLAY.read_text(encoding="utf-8"))


def dismissals() -> list[str]:
    """Every way to close the panel that the source mentions, or nothing."""
    return [written for written in NO_WAY_TO_DISMISS if written in card()]


def ways_out() -> list[str]:
    """Every way off this panel that the source mentions, or nothing."""
    return [written for written in NO_WAY_OUT if written in card()]


# --- no control at all: neither a dismiss nor a way out -----------------------

def test_the_card_offers_no_control_of_its_own() -> None:
    """Zero, not one: the link to the run's own page was removed on 2026-09-18."""
    assert BUTTON.findall(card()) == []


def test_the_card_names_no_other_way_out_either() -> None:
    """A button is not the only shape an exit takes, so the prop and the anchor are named too."""
    assert ways_out() == []


def test_the_card_carries_no_way_to_dismiss_itself() -> None:
    """An audit cannot be cancelled, so a dismiss would hide a run that is still going."""
    assert dismissals() == []


def test_the_sweep_read_a_component_and_not_an_empty_file() -> None:
    """Non-vacuity: an unreadable component would satisfy every absence check above."""
    assert len(re.findall(r"<[A-Za-z]", card())) >= MINIMUM_ELEMENTS


def test_a_dismiss_added_to_the_card_would_be_reported_by_name() -> None:
    """Planted: the absence check above is an empty list either way."""
    assert [written for written in NO_WAY_TO_DISMISS
            if written in 'onClick={onClose}'] == ["onClose"]


def test_a_control_put_back_on_the_card_would_be_counted() -> None:
    """Planted: an empty list is what a regex that matched nothing returns too."""
    assert len(BUTTON.findall('<button type="button">Open this run</button>')) == 1


def test_the_exit_that_was_removed_would_be_reported_by_name() -> None:
    """Planted: the same empty list, for the exits that are not buttons."""
    assert [written for written in NO_WAY_OUT
            if written in '<button onClick={onOpenRun}>'] == ["onOpenRun"]
