"""Which kind of file goes where: HTML into a frame that grants nothing, everything else into a `<pre>`.

`FileViewer.jsx` shows one artifact on the page, and the whole of its design is
one split. HTML is a document and has to be *rendered*, which means handing
audited bytes to a browser -- so it goes into the sandboxed frame
`test_frame_sandbox.py` is about. Everything else is *text*, and goes into a
`<pre>` as a React child, which React escapes. **That is why the split exists**:
a `findings.json` holding `<script>alert(1)</script>` -- and a finding's title is
copied out of the audited repository -- must be shown and never run.
`test_file_viewer_kinds.py` shows that `readable` hands that markup through
untouched, so what decides its fate is the element it is handed to, which is
what this file reads.

**The refusal is by suffix, before a byte is fetched.** A `.pdf` or the archive
read as text is a screenful of mojibake, which looks like a corrupt file rather
than a viewer that was asked the wrong question. So the fetch effect is guarded
on the kind, and source order is asserted: a guard written after the request is
not a guard.

**The viewer names no file.** The card it replaced framed `report.html` and
`remediation.html` by name; this one keys on the suffix, so the sandbox now
covers *any* HTML a run leaves behind -- a wider surface than before, and one
that stays wide when a seventeenth artifact is added. That no artifact name
appears in the component is how that is held, against the real list in
`src/artifacts/names.py` rather than a transcription of it.

What text cannot show is the element tree: a `<pre>` and an `<iframe>` are read
here as the element each branch *opens*, and a branch rewritten to nest one
inside the other would pass. No test in this suite renders React, which is a
recorded defect and not one this file closes.

Reads one component as text. No fastapi, no node, no build.
"""

import re

from artifacts.names import ALL_NAMES

from .jsx_sweep import FRONTEND_SRC, strip_comments

VIEWER = FRONTEND_SRC / "components" / "FileViewer.jsx"

# Each branch's condition together with the element it opens. `[^(]*` reaches
# the parenthesis that opens the body -- the rest of the condition holds none --
# so a branch that opened the other element does not merely fail, it reports
# which element it found.
RENDERED_BRANCH = re.compile(r"how === RENDERED[^(]*\(\s*<(\w+)")
TEXT_BRANCH = re.compile(r"how !== RENDERED[^(]*\(\s*<(\w+)")

# What each branch has to open, and the two ways markup could reach the page
# instead of being escaped.
THE_FRAME = "iframe"
THE_TEXT_ELEMENT = "pre"
AS_A_CHILD = ">{readable(text, how)}<"
UNESCAPED = ("srcDoc", "dangerouslySetInnerHTML")

# The effect that fetches, its guard, and the call the guard has to come before.
EFFECT = re.compile(r"useEffect\(\(\) => \{(.*?)\}, \[([^\]]*)\]\);", re.DOTALL)
THE_GUARD = "if (!how) return"
THE_FETCH = "fetchArtifactText"

# What a refused file gets instead: a sentence, and the name it is about. A
# viewer that refuses silently shows an empty card.
THE_REFUSAL = "{!how && ("
DOWNLOAD_INSTEAD = "Download it"

# Floors, so a file this test failed to read cannot pass the absence checks.
# Sixteen names today, and `test_artifact_inventory.py` is what holds that
# count against the writers -- here it only has to be a real list.
MINIMUM_ELEMENTS = 5
LEAST_ARTIFACT_NAMES = 16

# Planted below: the same two branches with their elements exchanged, which is
# the failure the readers exist to catch and the one a class-name sweep or a
# `sandbox=""` check could not see.
BRANCHES_EXCHANGED = (
    "{how === RENDERED && text !== null && (\n"
    '  <pre className="viewer__text mono">{readable(text, how)}</pre>\n'
    ")}\n"
    "{how && how !== RENDERED && text !== null && (\n"
    '  <iframe className="viewer__frame" sandbox="" srcDoc={text} title={name} />\n'
    ")}\n")


def viewer() -> str:
    """The viewer's own source, comments stripped: its docstring names every decision."""
    return strip_comments(VIEWER.read_text(encoding="utf-8"))


def element_opened_by(branch: re.Pattern, text: str) -> str:
    """The element one branch opens, or say that the branch is not there to read."""
    found = branch.search(text)
    assert found, f"{VIEWER.name} has no branch matching {branch.pattern}"
    return found.group(1)


def fetch_effect() -> str:
    """The body of the effect that reads the file, or say it is not there."""
    found = EFFECT.search(viewer())
    assert found, f"{VIEWER.name} declares no useEffect this test can read"
    return found.group(1)


def text_branch_onward() -> str:
    """The source from the text branch's condition to the end of the component."""
    text = viewer()
    assert "how !== RENDERED" in text, f"{VIEWER.name} no longer has a text branch"
    return text[text.index("how !== RENDERED"):]


def artifact_names_written_in_the_viewer() -> list[str]:
    """Every file a run can leave behind that the component names in its code."""
    text = viewer()
    return sorted(name for name in ALL_NAMES if name in text)


# --- HTML is rendered, in the frame that grants nothing -----------------------

def test_the_html_branch_opens_a_frame() -> None:
    """A document has to be rendered, so audited bytes go to a browser -- inside a sandbox."""
    assert element_opened_by(RENDERED_BRANCH, viewer()) == THE_FRAME


def test_the_frame_is_reached_by_suffix_and_not_by_file_name() -> None:
    """The widening: the deleted card framed two named files; this covers any HTML a run writes."""
    assert artifact_names_written_in_the_viewer() == []


def test_the_name_sweep_read_the_real_list_of_artifacts() -> None:
    """Non-vacuity: an empty allowlist would satisfy the check above having compared nothing."""
    assert len(ALL_NAMES) == len(set(ALL_NAMES)) >= LEAST_ARTIFACT_NAMES


# --- and everything else is text, which React escapes -------------------------

def test_the_text_branch_opens_a_pre() -> None:
    """The claim the split exists for: a json document carrying markup is shown, not run."""
    assert element_opened_by(TEXT_BRANCH, viewer()) == THE_TEXT_ELEMENT


def test_the_bytes_are_handed_to_the_pre_as_a_child() -> None:
    """A React child is escaped; the same string in an attribute below would not be."""
    assert AS_A_CHILD in viewer()


def test_the_text_branch_sets_no_markup_of_its_own() -> None:
    """Both ways round the escaping, named: the text path may use neither."""
    assert [written for written in UNESCAPED if written in text_branch_onward()] == []


def test_the_two_branches_would_be_reported_if_they_were_exchanged() -> None:
    """Mutation check: each reader names the element it found, so a swap fails loudly."""
    assert element_opened_by(RENDERED_BRANCH, BRANCHES_EXCHANGED) == THE_TEXT_ELEMENT
    assert element_opened_by(TEXT_BRANCH, BRANCHES_EXCHANGED) == THE_FRAME


# --- a file it cannot show is refused before it is read -----------------------

def test_the_fetch_is_guarded_on_the_kind() -> None:
    """A PDF read as text is mojibake, which reads as a corrupt file rather than a wrong question."""
    body = fetch_effect()
    assert body.strip().startswith(THE_GUARD)
    assert THE_FETCH in body


def test_the_guard_comes_before_the_request() -> None:
    """Said as order, because a guard written after the fetch is not a guard."""
    body = fetch_effect()
    assert body.index(THE_GUARD) < body.index(THE_FETCH)


def test_a_refused_file_is_told_what_to_do_instead() -> None:
    """A silent refusal is an empty card, which reads as a viewer that broke."""
    assert THE_REFUSAL in viewer()
    assert DOWNLOAD_INSTEAD in viewer()


def test_the_sweep_read_a_component_and_not_an_empty_file() -> None:
    """Non-vacuity: an unreadable component would satisfy the absence checks above."""
    assert len(re.findall(r"<[A-Za-z]", viewer())) >= MINIMUM_ELEMENTS
    assert fetch_effect().strip()
