"""The run overlay's one control is a way out rather than a cancel, and it decides nothing else.

`RunOverlay.jsx` is the card an audit advances in, rendered on the shared
`Modal.jsx` -- a fixed, covering panel while a run is going, and
`test_css_overlay.py` holds the stylesheet that makes it so. What is asserted
here is what the *run overlay* decides; the dialog markup it used to write
itself -- `role`, `aria-modal`, `aria-labelledby` and the close control -- moved
into the modal, and `test_modal_contract.py` holds it there. The claims did not
change with the file, but which file answers for them did, and a test left
pointing at the old one reads as a passing guard over nothing.

**It cannot be closed, and that is the honest position rather than an
oversight.** An audit cannot be cancelled -- the page has no endpoint for it and
`docs/TODO.md` records why -- so a dismiss would hide a run that carries on,
with the Audit button still disabled and nothing on screen saying why. The way
that is now *expressed* is by passing the modal no `onClose`, which is why
`test_modal_contract.py` asserts the pairing across both consumers and this file
asserts that the panel mentions no dismiss of its own.

What it has instead is **one exit and not zero**: the scrim covers the nav bar
too, so refusing to let a reader leave would strand them for the length of a
multi-minute audit. The single button opens this run's own page, which renders a
running run and keeps polling -- nothing is lost by taking it, and it is not a
cancel. One button, measured, because the close control the modal may render is
not this panel's and must not be counted as its exit.

**And the poll error is rendered inside the card.** That is the fix recorded in
`test_jsx_audit_page_outcomes.py`, which holds the other half -- that the page
body no longer renders it. Here it is source order only: text can show that the
notice comes after the modal element opens, and cannot show the element tree, so
a notice moved outside the card but still after it in the file would pass. No
test in this suite renders React -- a recorded defect -- and this is one of the
places that costs something.

Reads one component as text. No fastapi, no node, no build.
"""

import re

from .jsx_sweep import FRONTEND_SRC, strip_comments

OVERLAY = FRONTEND_SRC / "components" / "RunOverlay.jsx"

# The card's one control, and the prop it calls. A button is spelled once here;
# the count is what carries the decision.
BUTTON = re.compile(r"<button\b")
THE_ONE_EXIT = "onClick={onOpenRun}"

# What a dismiss would be written as, on this panel's side: the prop it would
# have to pass the modal, and the state a dismiss would carry. Not a general ban
# on effects -- a focus trap is an effect a modal may well need -- and not a ban
# on the modal having a close control, only on this caller asking for one.
NO_WAY_TO_DISMISS = ("onClose", "onDismiss", "Escape", "useState(")

# The title, and the fallback that has to be there: `app` is null until the
# audit has resolved the repository, which is most of the time this panel is on
# screen, so a card titled from `app` alone would open blank.
THE_TITLE = "record.app ?? record.repo_url"

# The card it renders on, the id it labels that card by, and the notice that must
# be inside it rather than under the scrim.
THE_CARD = "<Modal"
TITLE_ID = re.compile(r'titleId="([^"]+)"')
THE_WAIT_NOTICE = 'className="notice notice--wait"'

# How a status comparison reads. The page decides which run gets this panel; the
# panel itself is handed a record and renders it.
STATUS_TEST = re.compile(r"status\s*(?:===|!==)\s*\w+")

# A floor, so a file this test failed to read cannot pass every check below.
MINIMUM_ELEMENTS = 5


def card() -> str:
    """The overlay's own source, comments stripped: its docstring names every decision."""
    return strip_comments(OVERLAY.read_text(encoding="utf-8"))


def label_target() -> str:
    """The id the panel labels its card by, or say the prop is missing."""
    found = TITLE_ID.search(card())
    assert found, f"{OVERLAY.name} passes no titleId, so the dialog has no name"
    return found.group(1)


def dismissals() -> list[str]:
    """Every way to close the panel that the source mentions, or nothing."""
    return [written for written in NO_WAY_TO_DISMISS if written in card()]


def position_of(fragment: str) -> int:
    """Where one fragment is in the source, or say plainly that it is not there."""
    text = card()
    assert fragment in text, f"{OVERLAY.name} no longer contains {fragment}"
    return text.index(fragment)


# --- what it renders itself ----------------------------------------------------

def test_the_panel_is_rendered_on_the_shared_modal() -> None:
    """Which is what makes `test_modal_contract.py` the file that answers for the dialog."""
    assert THE_CARD in card()


def test_the_card_is_titled_before_the_app_name_is_known() -> None:
    """`app` is null until the repository is resolved, which is most of this panel's life."""
    assert THE_TITLE in card()


def test_the_panel_names_the_id_its_card_is_labelled_by() -> None:
    """The modal renders `id={titleId}`; a caller that passes none leaves it undefined."""
    assert label_target()


# --- one exit, and no way to dismiss a run that carries on --------------------

def test_the_card_offers_exactly_one_control() -> None:
    """One exit and not zero: the scrim covers the nav bar, so leaving has to be possible."""
    assert len(BUTTON.findall(card())) == 1


def test_the_one_control_opens_the_run_and_does_not_close_the_panel() -> None:
    """It is a way to the run's own page, which keeps polling -- not a cancel."""
    assert THE_ONE_EXIT in card()


def test_the_card_carries_no_way_to_dismiss_itself() -> None:
    """An audit cannot be cancelled, so a dismiss would hide a run that is still going."""
    assert dismissals() == []


# --- what it renders, and what it decides -------------------------------------

def test_the_poll_error_is_rendered_inside_the_card() -> None:
    """Source order: the message that arrives during a run is not under the scrim."""
    assert position_of(THE_CARD) < position_of(THE_WAIT_NOTICE)


def test_the_card_decides_nothing_about_which_run_it_is_for() -> None:
    """The page gates it on `running`; a second status branch here would be a second rule."""
    assert STATUS_TEST.findall(card()) == []


def test_the_sweep_read_a_component_and_not_an_empty_file() -> None:
    """Non-vacuity: an unreadable component would satisfy the absence checks above."""
    assert len(re.findall(r"<[A-Za-z]", card())) >= MINIMUM_ELEMENTS
    assert label_target()


def test_a_dismiss_added_to_the_card_would_be_reported_by_name() -> None:
    """Planted: the absence check above is an empty list either way."""
    assert [written for written in NO_WAY_TO_DISMISS
            if written in 'onClick={onClose}'] == ["onClose"]
