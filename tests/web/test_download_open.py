"""Each file in the list is two controls, and the one that cannot work is absent rather than dead.

`DownloadPanel.jsx` used to be one link per file. It is two controls now: the
name opens the file on the page, the arrow saves it. A row that only downloaded
meant reading a 300-byte json document took a round trip through the
filesystem, and a row that only viewed would have no answer for a PDF.

**Where the file cannot be shown, the open control is not rendered at all.** Not
a disabled button, not a greyed eye: `howToShow` returns null for `report.pdf`
and for the archive, and the affordance goes with it. A disabled control invites
a click, answers it with nothing, and says nothing about why -- and a reader
cannot tell a control that is disabled for a reason from one disabled by a bug.
That is the claim with the mutation test under it, because "renders no button"
is satisfied by a row that renders nothing at all: the refused row is asserted
to still carry the file's name *and* its download link.

**One decision, in one place.** Which names are viewable is `FileViewer.jsx`'s
answer and the panel imports it, so the eye and the frame can never disagree
about what `.html` means. A second suffix table here is the failure that would
put an eye on a file the viewer then refuses -- so no suffix is written in this
component at all, checked against the suffix constants in
`src/artifacts/names.py`.

What text cannot see is the rendered row: whether the button is reachable by
keyboard, and what the two controls look like side by side. No test in this
suite renders React, a recorded defect this file does not close.

Reads one component as text. No fastapi, no node, no build.
"""

import re

from artifacts.names import HTML_SUFFIX, MARKDOWN_SUFFIX, PDF_SUFFIX

from .icon_tables import icon_names
from .jsx_sweep import FRONTEND_SRC, strip_comments

PANEL = FRONTEND_SRC / "components" / "DownloadPanel.jsx"

# The row's two halves, read as the ternary that chooses between them. Neither
# branch holds a `) : (` or a `)}` of its own, which is what keeps the
# non-greedy groups on the real boundaries.
THE_ROW = re.compile(r"howToShow\(file\.name\) \? \((.*?)\) : \((.*?)\)\}", re.DOTALL)

# What only the viewable half may have, and what neither half may have.
THE_OPEN_CONTROL = "<button"
THE_EYE = "eye"
DEAD_CONTROL = ("disabled", "aria-disabled")

# What every row carries whether the file can be shown or not: the name, and the
# link that saves it.
THE_NAME = "{file.name}"
THE_SAVE_LINK = 'className="download__save"'

# Where the decision is made, and how it is asked for. A `.jsx` extension in the
# specifier because that is how every other import in this page is written.
THE_ONE_DECISION = 'import FileViewer, { howToShow } from "./FileViewer.jsx";'

# No suffix may be written here, or the eye and the frame could disagree about
# what a name means. `names.py` has constants for three of the four; json is
# spelled out because nothing there names it on its own.
JSON_SUFFIX = ".json"
SUFFIXES = (JSON_SUFFIX, MARKDOWN_SUFFIX, HTML_SUFFIX, PDF_SUFFIX)

# How the viewer is opened, and what it is told to show.
OPENS_THE_ROW = "setViewing(file.name)"
SHOWS_WHAT_WAS_OPENED = "name={viewing}"

# A floor under each branch, so a ternary this test mis-read cannot pass the
# absence checks by returning two empty strings.
MINIMUM_BRANCH = 60

# Planted below: the refused half as a disabled button, which is the shape this
# file exists to rule out and the one that satisfies "the row is still there".
PLANTED_DISABLED = (
    "{howToShow(file.name) ? (\n"
    '  <button type="button" className="download__open"\n'
    "          onClick={() => setViewing(file.name)}>\n"
    '    <Icon name="eye" />\n'
    "  </button>\n"
    ") : (\n"
    '  <button type="button" className="download__open" disabled>\n'
    '    <span className="download__name mono">{file.name}</span>\n'
    "  </button>\n"
    ")}\n")


def panel() -> str:
    """The panel's own source, comments stripped: they name a PDF and a suffix in prose."""
    return strip_comments(PANEL.read_text(encoding="utf-8"))


def branches_of(text: str) -> tuple[str, str]:
    """The two halves of the row: what a viewable file gets, and what a refused one gets."""
    found = THE_ROW.search(text)
    assert found, "no `howToShow(file.name) ? ... : ...` row this test can read"
    return found.group(1), found.group(2)


def viewable_half() -> str:
    """What a file the viewer can show is rendered as, in the real panel."""
    return branches_of(panel())[0]


def refused_half() -> str:
    """What a file the viewer refuses is rendered as, in the real panel."""
    return branches_of(panel())[1]


def suffixes_written_here() -> list[str]:
    """Every file suffix the panel names in its own code, or nothing."""
    return [suffix for suffix in SUFFIXES if suffix in panel()]


# --- the viewable file gets a control -----------------------------------------

def test_a_file_the_viewer_can_show_gets_an_open_control() -> None:
    """Non-vacuity for everything below: something has to render the button."""
    assert THE_OPEN_CONTROL in viewable_half()


def test_the_open_control_carries_the_eye_the_icon_set_draws() -> None:
    """A name with no path draws the fallback square, which is not an affordance."""
    assert f'name="{THE_EYE}"' in viewable_half()
    assert THE_EYE in icon_names()


def test_the_control_opens_the_row_it_is_on() -> None:
    """One state for the whole list, so the name it is set to is what has to be shown."""
    assert OPENS_THE_ROW in panel()
    assert SHOWS_WHAT_WAS_OPENED in panel()


# --- and the refused file gets no control, rather than a dead one --------------

def test_a_file_the_viewer_refuses_gets_no_open_control() -> None:
    """Absent, not disabled: a control that answers a click with nothing explains nothing."""
    assert THE_OPEN_CONTROL not in refused_half()


def test_the_refused_half_renders_nothing_disabled() -> None:
    """Said the other way too, because a disabled span is as unclickable and as puzzling."""
    assert [written for written in DEAD_CONTROL if written in refused_half()] == []


def test_the_refused_row_still_shows_the_files_name() -> None:
    """What makes the two checks above mean something: the row is there, the eye is not."""
    assert THE_NAME in refused_half()


def test_every_row_keeps_the_link_that_saves_the_file() -> None:
    """A PDF cannot be shown and must still be downloadable, which is the point of the pair."""
    assert THE_SAVE_LINK in panel()
    assert THE_SAVE_LINK not in viewable_half()
    assert THE_SAVE_LINK not in refused_half()


def test_a_disabled_control_in_the_refused_half_would_be_reported() -> None:
    """Mutation check: both absence checks above pass over an empty branch either way."""
    planted = branches_of(PLANTED_DISABLED)[1]
    assert THE_OPEN_CONTROL in planted
    assert [written for written in DEAD_CONTROL if written in planted] == ["disabled"]


# --- and which files are viewable is decided in one place ---------------------

def test_the_panel_asks_the_viewer_which_names_it_can_show() -> None:
    """The import is the join: the eye and the frame cannot disagree about `.html`."""
    assert THE_ONE_DECISION in panel()


def test_the_panel_writes_no_suffix_of_its_own() -> None:
    """A second table here is how an eye appears on a file the viewer then refuses."""
    assert suffixes_written_here() == []


def test_the_row_reader_read_two_real_branches() -> None:
    """Non-vacuity: a mis-read ternary would hand every check above two empty strings."""
    assert len(viewable_half()) >= MINIMUM_BRANCH
    assert len(refused_half()) >= MINIMUM_BRANCH
