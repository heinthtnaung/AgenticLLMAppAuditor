"""The shared modal announces itself, and its dismiss is optional on purpose.

`Modal.jsx` is the fixed scrim and the one card on it, extracted when a second
thing needed one: the run overlay and the file viewer. The dialog markup moved
with it -- `role`, `aria-modal`, `aria-labelledby` and the close control were all
written in `RunOverlay.jsx` before -- so the claims `test_jsx_overlay_card.py`
used to make about that file are made here, over the file that now makes them,
and that file keeps only what the run overlay itself decides.

**`onClose` is optional, and its absence is the decision.** The run overlay
passes none, because an audit cannot be cancelled and a dismiss would hide a run
that carries on; the file viewer passes one, because closing a document changes
nothing. So two things have to hold together and neither is safe alone: the
close control exists only under the prop, *and* the Escape listener is bound only
under it. A modal that rendered no button but still bound Escape would be
dismissable by keyboard with nothing on screen saying so -- invisible in a
screenshot, and exactly the case with teeth.

**What the consumers pass is what the modal takes apart, in both directions.**
A prop passed that the component does not destructure, and a prop destructured
that nobody passes, are both `undefined`, and React renders `undefined` as
nothing at all: no throw, no warning, an empty place on the page. That is the
boundary `test_jsx_overlay_props.py` holds between the audit page and the run
overlay, and it applies here with a second consumer and one extra trap --
`wide` is passed as a **shorthand** attribute with no value, so a reader that
only matched `name={...}` would report it as a prop nobody passes and a rename
of it as nothing at all. `children` is the reverse exemption and the only one:
JSX nesting supplies it, so it is destructured and never written as an
attribute.

**The label has to point at something.** `aria-labelledby` naming an id no
element carries is an unlabelled dialog: valid markup, silently useless, and
invisible to everyone who is not using a screen reader. Here that is a claim
about two files at once -- `Modal` renders `id={titleId}` and each consumer
supplies the value -- so both halves are read, and a consumer that forgot the
prop would hand `undefined` to the attribute, which React drops entirely.

What this cannot see: whether the dialog traps focus, and whether Escape really
reaches the handler in a browser. Both need a rendered page, and no test in this
suite renders React -- a recorded defect this file does not close. What is
deliberately *not* barred is an effect added for a focus trap; what is read is
the effect that closes.

Reads three components as text. No fastapi, no node, no build.
"""

import re

from .icon_tables import icon_names
from .jsx_sweep import FRONTEND_SRC, strip_comments

COMPONENTS = FRONTEND_SRC / "components"
MODAL = COMPONENTS / "Modal.jsx"

# Who uses it, and whether each one passes a way to close. The run overlay's
# `False` is the case this file exists for.
CONSUMERS = {"RunOverlay.jsx": False, "FileViewer.jsx": True}

# What the panel claims to be, as the attributes a screen reader reads.
DIALOG_ROLE = 'role="dialog"'
MODAL_ATTRIBUTE = 'aria-modal="true"'

# The label, the id it has to name, and the prop both are built from.
LABELLED_BY = 'aria-labelledby={titleId}'
ELEMENT_ID = 'id={titleId}'
TITLE_ID_PROP = re.compile(r'titleId="([^"]*)"')

# One `<Modal ...>` element with its props. An opening tag, because the card
# takes children: `title={record.app ?? record.repo_url}` holds no `>`.
MODAL_ELEMENT = re.compile(r"<Modal\b([^>]*?)>", re.DOTALL)
PROP_NAME = re.compile(r"(\w+)=[{\"]")

# A prop with a value, removed so that whatever words are left are the shorthand
# ones -- `wide`, which is how JSX spells `wide={true}` and is invisible to the
# pattern above.
VALUED_PROP = re.compile(r'\w+=(?:\{[^{}]*\}|"[^"]*")')

# What the component takes apart, on one line, and the one name that is never
# passed as an attribute: JSX nesting is what supplies `children`.
PROPS_TAKEN = re.compile(r"function Modal\(\{([^}]*)\}\)")
FROM_NESTING = "children"

# The close control, matched together with the condition that renders it, so a
# button rendered unconditionally does not match at all.
GUARDED_CLOSE = re.compile(r"\{onClose && \(\s*<button\b", re.DOTALL)
BUTTON = re.compile(r"<button\b")

# The effect that binds Escape, read as its body and its dependency list.
EFFECT = re.compile(r"useEffect\(\(\) => \{(.*?)\}, \[([^\]]*)\]\);", re.DOTALL)
THE_GUARD = "if (!onClose) return"
THE_KEY = '"Escape"'
BINDS = "addEventListener"
UNBINDS = "removeEventListener"

# The icon-only button needs a name a screen reader can read, and a glyph the
# set really has.
CLOSE_LABEL = 'aria-label="Close"'
CLOSE_ICON = "close"

# The shorthand prop, and which consumer passes it: the file viewer wants more
# of the window than a run does.
THE_SHORTHAND_PROP = "wide"
THE_WIDE_CONSUMER = "FileViewer.jsx"

# Floors, so a file this test failed to read cannot satisfy the absence checks.
# Five props today, taken and passed.
MINIMUM_ELEMENTS = 4
MINIMUM_PROPS = 4

# Planted below: a prop no component destructures, which renders as nothing.
A_PROP_NOBODY_TAKES = "footer"

# Planted below, because two of the checks above pass over an absence either way.
CLOSE_WITH_NO_CONDITION = '<button type="button" className="overlay__close" />'
EFFECT_WITH_NO_GUARD = ('useEffect(() => {\n  window.addEventListener("keydown", close);\n'
                        '}, [onClose]);')


def modal() -> str:
    """The modal's own source, comments stripped: its docstring names every decision."""
    return strip_comments(MODAL.read_text(encoding="utf-8"))


def effect_body(text: str) -> str:
    """The body of the one effect the modal declares, or say it is not there."""
    found = EFFECT.search(text)
    assert found, "Modal.jsx declares no useEffect this test can read"
    return found.group(1)


def effect_dependencies(text: str) -> list[str]:
    """What the effect re-runs on, read off the same declaration."""
    found = EFFECT.search(text)
    assert found, "Modal.jsx declares no useEffect this test can read"
    return [name.strip() for name in found.group(2).split(",") if name.strip()]


def props_passed_by(where: str) -> set[str]:
    """Every prop one consumer hands the modal, valued or shorthand."""
    text = strip_comments((COMPONENTS / where).read_text(encoding="utf-8"))
    found = MODAL_ELEMENT.search(text)
    assert found, f"{where} does not render <Modal ...> as one opening tag"
    shorthand = VALUED_PROP.sub(" ", found.group(1)).split()
    assert all(word.isidentifier() for word in shorthand), (
        f"{where} passes a prop shape this reader cannot take apart: {shorthand}")
    return set(PROP_NAME.findall(found.group(1))) | set(shorthand)


def props_passed_by_anyone() -> set[str]:
    """Every prop any consumer hands the modal."""
    return set().union(*(props_passed_by(where) for where in CONSUMERS))


def props_taken() -> set[str]:
    """Every prop the modal takes apart, read off the component itself."""
    found = PROPS_TAKEN.search(modal())
    assert found, "Modal.jsx no longer destructures its props on one line"
    return {name.strip() for name in found.group(1).split(",") if name.strip()}


def title_ids() -> dict[str, str]:
    """The id each consumer says its dialog is labelled by."""
    found: dict[str, str] = {}
    for where in CONSUMERS:
        text = strip_comments((COMPONENTS / where).read_text(encoding="utf-8"))
        said = TITLE_ID_PROP.search(text)
        assert said, f"{where} passes no titleId, so its dialog has no name"
        found[where] = said.group(1)
    return found


# --- it announces itself as a modal dialog -------------------------------------

def test_the_card_is_announced_as_a_modal_dialog() -> None:
    """A covering panel that is not announced is a page a reader cannot find their way out of."""
    assert DIALOG_ROLE in modal()
    assert MODAL_ATTRIBUTE in modal()


def test_the_label_and_the_id_are_built_from_the_same_prop() -> None:
    """An id nothing carries is an unlabelled dialog, and nothing says so at runtime."""
    assert LABELLED_BY in modal()
    assert ELEMENT_ID in modal()


def test_every_consumer_supplies_the_id_the_label_points_at() -> None:
    """A consumer that forgot the prop hands `undefined` to the attribute, which React drops."""
    assert sorted(title_ids()) == sorted(CONSUMERS)
    assert [where for where, value in title_ids().items() if not value] == []


# --- the dismiss is optional, and both halves of it move together --------------

def test_the_close_control_is_rendered_only_under_the_prop() -> None:
    """One button, and it exists only when there is something for it to do."""
    assert len(BUTTON.findall(modal())) == 1
    assert GUARDED_CLOSE.search(modal())


def test_the_escape_listener_is_bound_only_under_the_prop() -> None:
    """The half a screenshot cannot show: a keyboard dismiss with no button beside it."""
    body = effect_body(modal())
    assert body.strip().startswith(THE_GUARD)
    assert THE_KEY in body
    assert BINDS in body


def test_the_escape_listener_is_taken_off_again() -> None:
    """A modal opened and closed ten times would otherwise leave ten live handlers."""
    assert UNBINDS in effect_body(modal())


def test_the_effect_re_runs_when_the_close_handler_changes() -> None:
    """It reads `onClose`; a dependency list without it binds the first one for ever."""
    assert "onClose" in effect_dependencies(modal())


def test_the_run_overlay_passes_no_way_to_close_and_the_file_viewer_does() -> None:
    """The pairing that gives the option its meaning: an audit cannot be cancelled."""
    assert {where: "onClose" in props_passed_by(where) for where in CONSUMERS} == CONSUMERS


# --- what is passed is what is taken apart, both ways -------------------------

def test_every_prop_a_consumer_passes_is_one_the_modal_takes_apart() -> None:
    """A prop the component does not destructure is `undefined`, and renders as nothing."""
    assert sorted(props_passed_by_anyone() - props_taken()) == []


def test_every_prop_the_modal_takes_apart_is_one_some_consumer_passes() -> None:
    """The other direction, with one exemption: JSX nesting supplies `children`."""
    assert sorted(props_taken() - props_passed_by_anyone() - {FROM_NESTING}) == []


def test_the_shorthand_prop_is_read_as_a_prop() -> None:
    """`wide` is written with no value at all, and is the one a `name={...}` reader misses."""
    assert THE_SHORTHAND_PROP in props_passed_by(THE_WIDE_CONSUMER)


def test_the_prop_sweep_read_both_sides() -> None:
    """Non-vacuity: two empty sets satisfy both comparisons above having read nothing."""
    assert len(props_passed_by_anyone()) >= MINIMUM_PROPS
    assert len(props_taken()) >= MINIMUM_PROPS


def test_a_prop_one_side_does_not_know_about_is_reported() -> None:
    """Planted: both comparisons above are empty sets either way."""
    planted = props_passed_by_anyone() | {A_PROP_NOBODY_TAKES}
    assert sorted(planted - props_taken()) == [A_PROP_NOBODY_TAKES]


# --- and the control a reader clicks can be read out loud ----------------------

def test_the_icon_only_close_button_carries_a_name() -> None:
    """An `<svg>` in a button is no accessible name at all."""
    assert CLOSE_LABEL in modal()


def test_the_close_glyph_is_one_the_icon_set_draws() -> None:
    """A name with no path draws the fallback square, which is not a close button."""
    assert f'name="{CLOSE_ICON}"' in modal()
    assert CLOSE_ICON in icon_names()


# --- the readers were read against a real component ---------------------------

def test_the_sweep_read_a_component_and_not_an_empty_file() -> None:
    """Non-vacuity: an unreadable component would satisfy the absence checks above."""
    assert len(re.findall(r"<[A-Za-z]", modal())) >= MINIMUM_ELEMENTS
    assert effect_body(modal()).strip()


def test_a_close_button_with_no_condition_on_it_would_not_match() -> None:
    """Planted: the guarded-close pattern is the whole claim, so it is shown to discriminate."""
    assert GUARDED_CLOSE.search(CLOSE_WITH_NO_CONDITION) is None
    assert len(BUTTON.findall(CLOSE_WITH_NO_CONDITION)) == 1


def test_an_effect_that_binds_escape_unconditionally_would_be_reported() -> None:
    """Planted: `startswith` on a body this test never read would pass on an empty string."""
    assert not effect_body(EFFECT_WITH_NO_GUARD).strip().startswith(THE_GUARD)
