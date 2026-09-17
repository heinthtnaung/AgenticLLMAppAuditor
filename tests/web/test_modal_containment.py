"""The modal is portalled to the body, and the chain that makes that load-bearing.

A screenshot showed the file viewer hanging off to the right of the Download
rail, measured from the rail rather than from the window, with the *page*
carrying a horizontal scrollbar. `position: fixed` resolves against the viewport
only while no ancestor establishes a containing block, and `.card` declares
`backdrop-filter: blur(14px)` -- so the scrim was laid out from that card's
top-left corner. `Modal.jsx` now returns `createPortal(..., document.body)`,
which takes the markup out from under every card on the page.

**The claim with teeth is not that it calls `createPortal`.** It is *why* it has
to, which is four separate facts in four files:

1. `.card` establishes a containing block, as `backdrop-filter`.
2. `RunSummary.jsx` renders the download panel inside one.
3. `DownloadPanel.jsx` is what opens the file viewer.
4. `FileViewer.jsx` renders it on the shared modal, and the modal portals.

Each is asserted, because a change to any one of them means the reasoning needs
re-checking -- the same join `test_css_viewer_frame.py` makes from a class back
to the component that renders it, and for the same reason: `.report-frame`
outlived its markup by a whole change under two tests that went on passing.

**One of those tests fires on a change that would also fix the bug**, and that is
deliberate. Drop `backdrop-filter` from `.card` and fact 1 fails, even though the
defect would be gone -- because what fails then is the *reason* this modal is
portalled, and the honest answer is to re-read the file rather than keep a portal
nobody can justify. `test_css_viewer_frame.py` has that shape already: it fails
if the exported report starts colouring itself, which would also fix the
invisible report.

**The chain is asserted to be the only one**, so the render sites are counted
rather than merely found: a second component rendering the panel or the viewer
would be an ancestry nothing here read. `test_css_fixed_ancestry.py` covers the
other direction -- every fixed element the page renders, portalled or not.

**And the portal is joined to the built bundle**, because `dist/` is committed:
a fix in the source that was never rebuilt ships the defect with the suite green,
and `test_built_page_shipped.py` joins class names only.

What no test here can do: **say whether the modal is actually centred on the
window.** Nothing in this suite renders a page, which is exactly how this shipped
green, and a portal that resolves correctly in the stylesheet can still be
misplaced by a rule nothing here reads. `docs/TODO.md` keeps that row.

Reads four components, the stylesheets and this project's own build output as
text. No fastapi, no node, no build step.
"""

import re
from pathlib import Path

from . import containing_blocks
from .containing_blocks import source_of
from .css_rules import FRONTEND_SRC, REPO_ROOT, rules_selecting

BUILT_BUNDLE = REPO_ROOT / "frontend" / "dist" / "assets" / "index.js"
COMPONENTS = FRONTEND_SRC / "components"
MODAL = COMPONENTS / "Modal.jsx"
VIEWER = COMPONENTS / "FileViewer.jsx"
PANEL = COMPONENTS / "DownloadPanel.jsx"
SUMMARY = COMPONENTS / "RunSummary.jsx"

# The scrim, and the declaration whose resolution the whole chain is about.
THE_SCRIM = ".overlay"

# The card the viewer is opened from, and the property that makes it a containing
# block. Named here so the failure says which declaration the portal answers.
THE_CARD_CLASS = "card"
THE_BLUR = "backdrop-filter"

# Where the markup has to end up for `position: fixed` to mean the window.
THE_PORTAL_TARGET = "document.body"
FROM_REACT_DOM = 'import { createPortal } from "react-dom";'

# The links of the chain, each as the element one file writes for the next.
THE_PANEL = "<DownloadPanel"
THE_VIEWER = "<FileViewer"
THE_MODAL = "<Modal"

# Who is allowed to render each link. A second render site means the ancestry
# this file reasons about is no longer the only one.
THE_PANELS_ONE_SITE = ["RunSummary.jsx"]
THE_VIEWERS_ONE_SITE = ["DownloadPanel.jsx"]

# An element closing between the card and the panel would mean the card is no
# longer open there. Its absence is a stronger claim than "the card comes first",
# and the limit is stated: a nested `<div>...</div>` before the panel would read
# here as the card closing, which is a false positive a reader resolves by
# looking.
CLOSING_DIV = "</div>"

# The same call after Vite has been over it. The local binding is renamed by the
# minifier, so the join is on the exported name and on the scrim's own class --
# which is as far as a text sweep of minified output can honestly go, and enough
# to tell a rebuilt bundle from the one that shipped the defect.
PORTAL_IN_THE_BUNDLE = re.compile(
    r"createPortal\)?\(.{0,120}?className:[`\"']overlay[`\"']", re.DOTALL)
TARGET_IN_THE_BUNDLE = ",document.body)"

# Floors, so a file this test failed to read cannot satisfy the checks above.
MINIMUM_ELEMENTS = 4

# Planted below, because three of the checks pass over an absence either way: a
# component that renders in place, a panel written after its card has closed, and
# the built bundle's own shape without a portal in it -- planted rather than
# mutated, because `dist/` is build output and no test edits it.
RENDERED_IN_PLACE = 'return (\n  <div className="overlay">{children}</div>\n);'
PANEL_AFTER_THE_CARD = ('<div className="card"><h2>Download</h2></div>\n'
                        "<DownloadPanel runId={record.run_id} />")
BUNDLE_WITHOUT_A_PORTAL = "(0,f.jsx)(`div`,{className:`overlay`,role:`dialog`})"


def attribute_positions(text: str, class_name: str) -> list[int]:
    """Where each static attribute carrying this class begins, in source order."""
    return [found.start() for found in containing_blocks.STATIC_CLASS.finditer(text)
            if class_name in found.group(1).split()]


def rendered_inside(text: str, class_name: str, element: str) -> bool:
    """Whether an element is written inside one carrying this class, with nothing closed between."""
    assert element in text, f"nothing here renders {element}"
    where = text.index(element)
    opened = [start for start in attribute_positions(text, class_name) if start < where]
    return bool(opened) and CLOSING_DIV not in text[opened[-1]:where]


def blurred_classes_in(component: Path) -> set[str]:
    """The classes one component writes that establish a containing block of their own."""
    return (containing_blocks.static_classes_in(component)
            & containing_blocks.classes_establishing_one())


def card_declarations() -> list[str]:
    """The properties that make `.card` a containing block, read off the stylesheet."""
    return [name for rule in rules_selecting(f".{THE_CARD_CLASS}")
            for name in containing_blocks.establishing_declarations(rule.block)]


# --- fact 1: the card the viewer opens from establishes a containing block -----

def test_the_scrim_is_positioned_against_the_viewport() -> None:
    """Which is the declaration every fact below is about: fixed, and so ancestor-sensitive."""
    assert THE_SCRIM in {rule.selector for rule in
                         containing_blocks.rules_fixed_to_the_viewport()}


def test_the_card_establishes_a_containing_block_for_anything_fixed_inside_it() -> None:
    """The premise. Drop the blur and this fails, which is the point: re-read the reasoning."""
    assert card_declarations() == [THE_BLUR], (
        f".{THE_CARD_CLASS} no longer establishes a containing block, so the "
        f"portal in {MODAL.name} may not be what keeps the modal on the window")


def test_the_card_is_the_one_such_class_the_run_summary_writes() -> None:
    """A second blurred ancestor would be a second path this file does not reason about."""
    assert blurred_classes_in(SUMMARY) == {THE_CARD_CLASS}


# --- fact 2: the download panel is rendered inside that card -------------------

def test_the_download_panel_is_rendered_inside_the_card() -> None:
    """Source order, and nothing closed in between: text cannot see the element tree."""
    assert rendered_inside(source_of(SUMMARY), THE_CARD_CLASS, THE_PANEL)


def test_nothing_but_the_run_summary_renders_the_download_panel() -> None:
    """A second site, in a card or out of one, means this ancestry is not the only one."""
    assert containing_blocks.components_rendering("DownloadPanel") == THE_PANELS_ONE_SITE


# --- fact 3: the panel is what opens the viewer, and the viewer uses the modal --

def test_the_download_panel_is_what_opens_the_file_viewer() -> None:
    """The link that puts the viewer under the card rather than under the page."""
    assert THE_VIEWER in source_of(PANEL)


def test_nothing_but_the_download_panel_renders_the_file_viewer() -> None:
    """Counted rather than found: the viewer opened from elsewhere has another ancestry."""
    assert containing_blocks.components_rendering("FileViewer") == THE_VIEWERS_ONE_SITE


def test_the_file_viewer_renders_on_the_shared_modal() -> None:
    """Which is what makes the portal below the thing that saves it."""
    assert THE_MODAL in source_of(VIEWER)


# --- fact 4: and the modal portals out of all of it ----------------------------

def test_the_modal_hands_its_markup_to_the_document_body() -> None:
    """The fix: a portal, not a removed blur, because any card would do this again."""
    assert containing_blocks.portals_to_the_body(MODAL)


def test_the_portal_target_is_the_body_and_not_a_node_inside_the_page() -> None:
    """A container mounted inside the app would sit under whatever establishes a block there."""
    found = containing_blocks.PORTAL_CALL.search(source_of(MODAL))
    assert found and found.group(1) == THE_PORTAL_TARGET


def test_the_portal_is_imported_from_react_dom() -> None:
    """`createPortal` lives in `react-dom`, not `react`: the wrong import is a build failure."""
    assert FROM_REACT_DOM in source_of(MODAL)


# --- and the bundle that is actually served carries it -------------------------

def test_the_built_bundle_hands_the_scrim_to_the_document_body() -> None:
    """`dist/` is committed: a source fixed and never rebuilt ships the defect, green."""
    assert BUILT_BUNDLE.is_file(), \
        f"no built bundle at {BUILT_BUNDLE}; run `npm run build` in frontend/"
    built = BUILT_BUNDLE.read_text(encoding="utf-8")
    assert PORTAL_IN_THE_BUNDLE.search(built), \
        "the built bundle portals no element called `overlay`"
    assert TARGET_IN_THE_BUNDLE in built


# --- and the readers were read against real components -------------------------

def test_the_sweep_read_the_components_and_not_empty_files() -> None:
    """Non-vacuity: an unreadable component satisfies every absence check above."""
    for component in (MODAL, VIEWER, PANEL, SUMMARY):
        assert len(re.findall(r"<[A-Za-z]", source_of(component))) >= MINIMUM_ELEMENTS, \
            component.name


def test_a_component_that_renders_in_place_is_not_read_as_portalling() -> None:
    """Planted: the portal check is one boolean, so it is shown to discriminate."""
    assert containing_blocks.PORTAL_CALL.search(RENDERED_IN_PLACE) is None


def test_a_bundle_that_renders_the_scrim_in_place_is_reported() -> None:
    """Planted: the bundle reader is shown to discriminate without editing build output."""
    assert PORTAL_IN_THE_BUNDLE.search(BUNDLE_WITHOUT_A_PORTAL) is None


def test_a_panel_rendered_after_its_card_has_closed_is_reported() -> None:
    """Planted: `rendered_inside` is the whole nesting claim, and source order alone would pass."""
    assert rendered_inside(PANEL_AFTER_THE_CARD, THE_CARD_CLASS, THE_PANEL) is False
