"""Audited content is never given the page's privileges: every frame grants nothing, and no page sets HTML.

This was `test_report_view.py`, whose subject was a card that framed
`report.html` and `remediation.html`. That card is gone and `FileViewer.jsx`
replaced it, which **widens what these two guards cover rather than narrowing
it**: the viewer decides by suffix, so *any* `.html` file a run leaves on disk
goes in the frame, named or not. The file was renamed with the claims rather
than deleted with the component -- deleting it would have dropped the only test
pinning `sandbox=""` at the moment that attribute started covering more.

The reason is unchanged. `report.html` is built from the audited repository's
own strings -- prompt text, file paths, finding titles -- and it is displayed by
a page served from the same origin as an API that clones anything it is asked to
and has no authentication.

- **`sandbox=""` grants nothing.** The attribute's value is an allow-list, and
  an empty one is the strongest form. `allow-scripts` and `allow-same-origin`
  *together* are equivalent to no sandbox at all -- the frame can reach out and
  remove its own sandbox attribute -- so neither is permitted anywhere, and the
  check is over every frame under `frontend/src/` rather than over the one this
  file knows about.
- **`srcDoc` appears only on a frame that grants nothing.** That is the property
  the check above rests on, said directly: the attribute is how audited bytes
  become a document, and it is the one form of "render this HTML" React does not
  make awkward. On an element that is not a sandboxed iframe it would be markup
  with the page's origin.
- **`dangerouslySetInnerHTML` appears nowhere under `frontend/src/`.** This is
  the guard that keeps the others honest after a later edit: the frame is only
  load-bearing while the HTML stays inside it, and the obvious way to "simplify"
  a frame away is to set the markup on a div. React makes that awkward on
  purpose and names the property accordingly; the name is what this searches for.

The markdown converter escapes all HTML today and a test elsewhere pins that
with a real script tag, so none of the three is load-bearing against the reports
as they are. They are load-bearing against that escaping being relaxed one
module away -- the kind of change nobody would think to re-check this page for.

Read as text, with comments stripped by `jsx_sweep.strip_comments`: there is no
JavaScript in this suite, and running it must not need Node. A comment naming
`dangerouslySetInnerHTML` to say why it is not used would otherwise be the
violation, which is a rule nobody agreed to -- the defect that file already
records about a comment naming a Python module.

Nothing here skips. It reads the committed JSX and nothing else.
"""

import re
from pathlib import Path

from .jsx_sweep import FRONTEND_SRC, strip_comments

# The frame audited HTML is shown in, and the attribute that says what it may do.
IFRAME = re.compile(r"<iframe\b[^>]*>", re.DOTALL)
SANDBOX = re.compile(r"""sandbox=(?:"([^"]*)"|'([^']*)'|\{([^}]*)\})""")

# What no frame may be granted. Together they are equivalent to no sandbox at
# all, so neither is allowed on its own -- a second edit would supply the other.
FORBIDDEN_GRANTS = ("allow-scripts", "allow-same-origin")

# What an empty `sandbox=""` splits into: nothing is granted. Named because
# `[]` and `[""]` are easy to confuse and only one of them is what the attribute
# means.
EMPTY_ALLOW_LIST: list[str] = []

# How audited bytes are handed to a browser as a document, and the React property
# that puts them in the page itself. Both named rather than matched loosely:
# these exact strings are the only two ways to do it.
SRC_DOC = "srcDoc"
UNESCAPED_HTML = "dangerouslySetInnerHTML"

# The component that shows the files, so the sweep is shown to have read the
# file whose behaviour this file is about.
FILE_VIEWER = "FileViewer.jsx"

# A floor under the sweep: one frame, measured, and zero frames would satisfy
# "every frame is sandboxed" perfectly.
LEAST_FRAMES = 1

# Planted sources, to prove each reader fires on a real violation.
PLANTED_FILE = "Planted.jsx"
PLANTED_UNSANDBOXED = '<iframe srcDoc={html} sandbox="allow-scripts allow-same-origin" />'
PLANTED_UNESCAPED = "<div dangerouslySetInnerHTML={{ __html: html }} />"
PLANTED_IN_A_COMMENT = f"// never use {UNESCAPED_HTML} here\n<div />"
PLANTED_SRC_DOC_ON_A_DIV = "<div srcDoc={text} />"


def jsx_under(root: Path) -> list[Path]:
    """Every JSX file under a tree, with the committed page as the default."""
    return sorted(root.rglob("*.jsx"))


def frames(root: Path = FRONTEND_SRC) -> list[tuple[str, str]]:
    """Every `<iframe ...>` the page declares, paired with the file that declares it."""
    found: list[tuple[str, str]] = []
    for source in jsx_under(root):
        text = strip_comments(source.read_text(encoding="utf-8"))
        found += [(source.name, tag) for tag in IFRAME.findall(text)]
    return found


def granted(tag: str) -> list[str]:
    """What one frame's sandbox attribute permits, or a marker when it has none."""
    said = SANDBOX.search(tag)
    if said is None:
        return ["no sandbox attribute at all"]
    value = next(group for group in said.groups() if group is not None)
    return value.split()


def files_naming(marker: str, root: Path = FRONTEND_SRC) -> list[str]:
    """Every file under a tree whose code names one string, comments excluded."""
    return sorted(source.name for source in jsx_under(root)
                  if marker in strip_comments(source.read_text(encoding="utf-8")))


def _without_safe_frames(text: str) -> str:
    """The same JSX with every frame that grants nothing taken out."""
    return IFRAME.sub(
        lambda found: "" if granted(found.group(0)) == EMPTY_ALLOW_LIST else found.group(0),
        text)


def src_docs_outside_a_sandboxed_frame(root: Path = FRONTEND_SRC) -> list[str]:
    """Every file in a tree that sets `srcDoc` on anything but a frame granting nothing."""
    found: list[str] = []
    for source in jsx_under(root):
        rest = _without_safe_frames(strip_comments(source.read_text(encoding="utf-8")))
        found += [source.name] * rest.count(SRC_DOC)
    return sorted(found)


def plant(tmp_path: Path, source: str) -> Path:
    """Write a throwaway page holding one offending component, and return its root."""
    root = tmp_path / "planted_src"
    root.mkdir()
    (root / PLANTED_FILE).write_text(source, encoding="utf-8")
    return root


# --- the sweep read something ----------------------------------------------------

def test_the_page_really_has_a_frame_to_check() -> None:
    """Guard: zero frames would satisfy "every frame grants nothing" perfectly."""
    assert len(frames()) >= LEAST_FRAMES


def test_the_component_that_shows_the_files_is_the_one_holding_it() -> None:
    """Named, so a renamed component cannot make the sweep pass by finding another frame."""
    assert FILE_VIEWER in {where for where, _ in frames()}


# --- every frame grants nothing ---------------------------------------------------

def test_every_frame_the_page_declares_is_sandboxed_to_nothing() -> None:
    """`sandbox=""` is an empty allow-list, which is the strongest form of the attribute."""
    assert [(where, granted(tag)) for where, tag in frames()
            if granted(tag) != EMPTY_ALLOW_LIST] == []


def test_no_frame_may_run_scripts_or_reach_this_origin() -> None:
    """Said as the two named grants, because together they are equivalent to no sandbox."""
    for where, tag in frames():
        assert not any(grant in tag for grant in FORBIDDEN_GRANTS), where


def test_that_reader_would_notice_a_frame_that_granted_them(tmp_path) -> None:
    """Mutation check: plant a frame with both grants and see the reader report them."""
    root = plant(tmp_path, PLANTED_UNSANDBOXED)
    assert [granted(tag) for _, tag in frames(root)] == [list(FORBIDDEN_GRANTS)]


def test_that_reader_would_notice_a_frame_with_no_sandbox_at_all(tmp_path) -> None:
    """The other failure: a missing attribute is not an empty one, and must not read as one."""
    root = plant(tmp_path, "<iframe srcDoc={html} />")
    assert [granted(tag) for _, tag in frames(root)] != [EMPTY_ALLOW_LIST]


# --- and audited bytes reach a browser only through one of them -------------------

def test_every_src_doc_on_the_page_is_on_a_frame_that_grants_nothing() -> None:
    """The attribute is how audited HTML becomes a document; elsewhere it carries this origin."""
    assert src_docs_outside_a_sandboxed_frame() == []


def test_one_component_and_one_only_hands_audited_bytes_to_a_browser() -> None:
    """An exact set, for the reason `src/` names its one connecting module: one place to audit.

    It is the non-vacuity of the check above as well -- a page with no `srcDoc`
    at all would satisfy it perfectly -- but the equality is the claim. A second
    component rendering audited HTML is the moment a person should look, and
    this is what makes it stop the suite rather than pass unnoticed.
    """
    assert files_naming(SRC_DOC) == [FILE_VIEWER]


def test_a_src_doc_on_something_that_is_not_a_frame_is_reported(tmp_path) -> None:
    """Mutation check: the comparison above is an empty list either way."""
    root = plant(tmp_path, PLANTED_SRC_DOC_ON_A_DIV)
    assert src_docs_outside_a_sandboxed_frame(root) == [PLANTED_FILE]


# --- and nothing sets markup on the page itself ------------------------------------

def test_no_component_puts_unescaped_markup_into_the_page() -> None:
    """The guard that keeps the frame honest: the obvious way round it is a div."""
    assert files_naming(UNESCAPED_HTML) == []


def test_that_search_would_notice_a_component_that_did(tmp_path) -> None:
    """Mutation check: plant one that sets HTML and see the search name its file."""
    assert files_naming(UNESCAPED_HTML, plant(tmp_path, PLANTED_UNESCAPED)) == [PLANTED_FILE]


def test_naming_it_in_a_comment_is_not_using_it(tmp_path) -> None:
    """Comments are stripped first, so explaining why it is not used stays possible."""
    assert files_naming(UNESCAPED_HTML, plant(tmp_path, PLANTED_IN_A_COMMENT)) == []
