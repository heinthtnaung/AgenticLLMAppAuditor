"""Two cards were removed from the run page, and a removal is what no sweep in this folder can see.

`ReportView.jsx` framed `report.html` and `remediation.html`; `EvidencePanel.jsx`
offered an upload. Both are gone, and **every join in this folder runs source to
bundle**: `test_built_page_shipped.py` looks for the source's class names in the
build and `test_built_styles_shipped.py` does the same for selectors, so a name
the source has *dropped* is invisible to both -- their own docstrings record it.
A deletion therefore needs an assertion on the source side or it is not checked
at all, which is what this file is.

**The report card went because it was a second way to read a subset of the file
list.** `report.html` and `remediation.html` are two of the sixteen files a run
writes, and the download panel now opens any of them by suffix --
`test_file_viewer_split.py` holds that widening, and the `sandbox=""` the card
depended on moved with it rather than being deleted with it.

**The evidence panel went because attaching a file changed no finding.** By
design: `web/uploads.py` says so at length, nothing under `src/` reads the
directory, and `findings.json` is untouched. So the page offered a control whose
only effect was on the page. What matters for a reader of this file is that the
*endpoint* stayed -- the record's `uploads` field and both routes are still
there and still tested next door -- because a control removed together with its
backend is a feature withdrawn, and a control removed from a page whose backend
stands is a page that stopped claiming something it could not deliver. The
difference is asserted rather than described.

**And the two headings are gone from the page, not just from those two files.**
The user asked for the `Report` section and the `Attached evidence` block to go;
a card moved to another component would satisfy every check above. So the card
titles are swept across the whole page. Only literal titles are read -- three
cards title themselves from a record -- which is a false negative this cannot
close by reading text.

Reads the JSX and one of the wrapper's modules as text, and imports the run
record, which needs no fastapi. No node, no build.
"""

import re

from run_record import RunRecord

from .icon_tables import icon_names
from .jsx_sweep import FRONTEND_SRC, strip_comments

REPO_ROOT = FRONTEND_SRC.parents[1]
SUMMARY = FRONTEND_SRC / "components" / "RunSummary.jsx"
UPLOAD_ROUTES = REPO_ROOT / "web" / "uploads.py"

# The two components that went, and the two headings they carried.
DELETED_COMPONENTS = ("ReportView.jsx", "EvidencePanel.jsx")
REMOVED_HEADINGS = ("Report", "Attached evidence")

# One card heading with literal text. The three cards titled from a record are
# not read: an expression is not a heading this can compare.
CARD_TITLE = re.compile(r'<h2 className="card__title"[^>]*>([^<{]+)</h2>')

# What a component renders, what it imports as a component, and what it defines
# itself. Read together, because a stale import and an undefined element are
# different failures and each is silent in its own way.
RENDERED = re.compile(r"<([A-Z]\w*)")
DEFAULT_JSX_IMPORT = re.compile(r'import (\w+) from "\./(\w+)\.jsx";')
LOCAL_COMPONENT = re.compile(r"function ([A-Z]\w*)\(")

# The icon the evidence panel asked for, which became dead data when it went.
THE_UPLOAD_ICON = "upload"

# The endpoint that stayed, as the two routes the wrapper declares. Read as text
# so this file needs no fastapi to say the backend was left alone.
KEPT_ROUTES = ('@app.post("/api/runs/{run_id}/uploads"',
               '@app.get("/api/runs/{run_id}/uploads/{upload_id}"')
KEPT_RECORD_FIELD = "uploads"

# Floors, so a sweep that read nothing cannot pass as a sweep that found no
# fault. Nine literal card titles and five imported components today.
MINIMUM_TITLES = 6
MINIMUM_COMPONENTS = 4

# Planted below: the heading as a card in another component, which is how a
# "removal" that was really a move would read.
PLANTED_HEADING = '<h2 className="card__title">Report</h2>'


def summary() -> str:
    """The run page's own source, comments stripped: they explain both removals in prose."""
    return strip_comments(SUMMARY.read_text(encoding="utf-8"))


def jsx_files() -> list:
    """Every component file the page ships, in a stable order."""
    return sorted(FRONTEND_SRC.rglob("*.jsx"))


def files_naming(marker: str) -> list[str]:
    """Every component whose code names one string, comments excluded."""
    return sorted(source.name for source in jsx_files()
                  if marker in strip_comments(source.read_text(encoding="utf-8")))


def card_titles() -> list[str]:
    """Every card heading the page writes as literal text, with its file."""
    found: list[str] = []
    for source in jsx_files():
        found += CARD_TITLE.findall(strip_comments(source.read_text(encoding="utf-8")))
    return [title.strip() for title in found]


def components_rendered() -> set[str]:
    """Every component element the run page renders."""
    return set(RENDERED.findall(summary()))


def components_imported() -> set[str]:
    """Every component the run page imports by default from a sibling file."""
    return {name for name, _ in DEFAULT_JSX_IMPORT.findall(summary())}


def components_defined() -> set[str]:
    """Every component the run page declares itself."""
    return set(LOCAL_COMPONENT.findall(summary()))


# --- the two components are gone, from the tree and from every caller ---------

def test_neither_deleted_component_is_still_on_disk() -> None:
    """The simplest half, and the one a source-to-bundle join can never report."""
    assert [name for name in DELETED_COMPONENTS
            if (FRONTEND_SRC / "components" / name).exists()] == []


def test_no_component_still_names_either_of_them() -> None:
    """A stale import fails the build; a stale element renders as undefined and says nothing."""
    for name in DELETED_COMPONENTS:
        assert files_naming(name.removesuffix(".jsx")) == [], name


def test_the_run_page_renders_exactly_the_components_it_imports() -> None:
    """Both directions at once: nothing dangling, and nothing imported that is never used."""
    assert components_rendered() - components_defined() == components_imported()


def test_the_component_sweep_read_a_real_page() -> None:
    """Non-vacuity: two empty sets satisfy the comparison above having read nothing."""
    assert len(components_imported()) >= MINIMUM_COMPONENTS
    assert components_defined()


# --- and their headings are gone from the whole page, not just from those files

def test_neither_removed_heading_titles_a_card_anywhere() -> None:
    """A card moved to another component would satisfy every check above."""
    assert [heading for heading in REMOVED_HEADINGS if heading in card_titles()] == []


def test_the_page_still_has_cards_with_headings_to_read() -> None:
    """Non-vacuity: a regex that matched nothing would clear the check above."""
    assert len(card_titles()) >= MINIMUM_TITLES


def test_the_heading_sweep_would_report_the_card_if_it_came_back() -> None:
    """Mutation check: the comparison above is an empty list either way."""
    assert CARD_TITLE.findall(PLANTED_HEADING) == [REMOVED_HEADINGS[0]]


def test_the_icon_the_evidence_panel_asked_for_went_with_it() -> None:
    """Dead data otherwise: a path in the table that no component ever draws."""
    assert THE_UPLOAD_ICON not in icon_names()
    assert files_naming(f'name="{THE_UPLOAD_ICON}"') == []


# --- while the backend the evidence panel used is untouched -------------------

def test_both_upload_routes_are_still_declared() -> None:
    """A control removed with its backend is a withdrawal; this was a page-side removal."""
    text = UPLOAD_ROUTES.read_text(encoding="utf-8")
    assert [route for route in KEPT_ROUTES if route not in text] == []


def test_the_run_record_still_carries_what_was_attached() -> None:
    """The field a later page could read again; nothing was demolished to hide a control."""
    assert KEPT_RECORD_FIELD in RunRecord.__dataclass_fields__
