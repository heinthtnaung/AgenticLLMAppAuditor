"""What the run overlay renders: the card, its name, and the one message that arrives mid-run.

`RunOverlay.jsx` is the card an audit advances in, rendered on the shared
`Modal.jsx` -- a fixed, covering panel while a run is going, and
`test_css_overlay.py` holds the stylesheet that makes it so. What is asserted
here is what the *run overlay* decides; the dialog markup it used to write
itself -- `role`, `aria-modal`, `aria-labelledby` and the close control -- moved
into the modal, and `test_modal_contract.py` holds it there. The claims did not
change with the file, but which file answers for them did, and a test left
pointing at the old one reads as a passing guard over nothing.

**Whether it can be closed or left is `test_jsx_overlay_exit.py`** -- no
dismiss and, since 2026-09-18, no exit. Split out because that one decision
carries two claims and two plants of its own, and this file would have crossed
the ~200-line rule with them in it: 153 lines before this change, and 204 had
the exit claims stayed. Split instead, so this file is 130.

**And the poll error is rendered inside the card.** That is the fix recorded in
`test_jsx_audit_page_outcomes.py`, which holds the other half -- that the page
body no longer renders it.

It was asserted as **source order** until 2026-09-18, and that was worthless:
`<Modal` is the *opening* tag, so everything later in the file is after it,
`</Modal>` included. Measured -- with the wait notice below the closing tag,
**all ten checks in this file passed**, on a page rendering the one message that
can arrive during a run underneath the scrim. The span between the tags is read
now. Still out of reach: a notice inside the element but nested under something
that hides it. Text can bound a span; it cannot render a tree.

Reads one component as text. No fastapi, no node, no build.
"""

import re

from .jsx_sweep import FRONTEND_SRC, strip_comments

OVERLAY = FRONTEND_SRC / "components" / "RunOverlay.jsx"

# The title, and the fallback that has to be there: `app` is null until the
# audit has resolved the repository, which is most of the time this panel is on
# screen, so a card titled from `app` alone would open blank. Written as the
# whole `title=` prop rather than as the expression: the fallback used for
# anything else in this file -- a heading, a tooltip -- would satisfy a check
# for the expression alone while the card opened with no name.
THE_TITLE = "title={record.app ?? record.repo_url}"

# The card it renders on, the id it labels that card by, and the notice that must
# be inside it rather than under the scrim. `THE_CARD_SPAN` is the whole element,
# opening tag to closing tag: the notice is required to be *within* it, because
# "after the opening tag" is true of the whole rest of the file.
THE_CARD = "<Modal"
THE_CARD_SPAN = re.compile(r"<Modal\b.*?</Modal>", re.DOTALL)
TITLE_ID = re.compile(r'titleId="([^"]+)"')
THE_WAIT_NOTICE = 'className="notice notice--wait"'

# The defect the span exists to refuse: the notice written below the closing
# tag, where it renders under the scrim. Every check in this file passed on it.
A_NOTICE_UNDER_THE_SCRIM = (
    '<Modal title={record.app} titleId="run-overlay-title">\n'
    '      <p className="card__hint mono">{record.repo_url}</p>\n'
    "    </Modal>\n"
    "    {error && (\n"
    '      <p className="notice notice--wait">Lost contact with the server.</p>\n'
    "    )}")

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


def card_contents(text: str) -> str:
    """Everything between the modal's own tags, or say the card is not one element."""
    found = THE_CARD_SPAN.search(text)
    assert found, f"no <{THE_CARD[1:]}>...</Modal> element to read"
    return found.group(0)


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


# --- what it renders, and what it decides -------------------------------------

def test_the_poll_error_is_rendered_inside_the_card() -> None:
    """Inside the element, not merely later in the file: under the scrim it is invisible."""
    assert THE_WAIT_NOTICE in card_contents(card())


def test_a_notice_written_below_the_closing_tag_is_not_accepted() -> None:
    """Planted: source order passed on exactly this page, with every other check green."""
    assert THE_WAIT_NOTICE not in card_contents(A_NOTICE_UNDER_THE_SCRIM)


def test_the_card_decides_nothing_about_which_run_it_is_for() -> None:
    """The page gates it on `running`; a second status branch here would be a second rule."""
    assert STATUS_TEST.findall(card()) == []


def test_the_sweep_read_a_component_and_not_an_empty_file() -> None:
    """Non-vacuity: an unreadable component would satisfy the absence checks above."""
    assert len(re.findall(r"<[A-Za-z]", card())) >= MINIMUM_ELEMENTS
    assert label_target()
