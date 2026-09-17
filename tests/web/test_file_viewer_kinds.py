"""Which files the viewer will show and how it shows them, run as the page's own code.

`FileViewer.jsx` decides by suffix: `howToShow(name)` answers `json`, `text`,
`html`, or **null for a file this page cannot show**. That last answer is the
interesting one -- it is a refusal made before a byte is fetched, because a PDF
or the archive read as text is a screenful of mojibake, which looks like a
corrupt file rather than a viewer asked the wrong question.

**Every name a run can leave behind is classified here, against the real list.**
The expectation below is written out name by name and then compared to
`src/artifacts/names.py` for completeness, so a seventeenth artifact fails this
file rather than quietly arriving with whatever its suffix happens to mean. The
pair `findings.sarif.json` and `findings.openvex.json` gets its own case: both
are json to a reader whatever their middle word says, and a table keyed on whole
names rather than suffixes is how that goes wrong.

**An unparseable json document is returned byte for byte, and that is the
decision rather than a fallback.** `readable` pretty-prints only on success,
because the thing a reader needs when a document will not parse is the broken
text and not a viewer's opinion of it -- a viewer that showed an error message
instead would hide the one thing worth seeing.

**It runs the module's head, not the whole file**, in the pattern
`test_model_status_reading.py` established: everything above the component is
plain JavaScript -- the three kind names, the suffix table, `howToShow` and
`readable` -- and the component itself is JSX, which node cannot read. The slice
is asserted to still hold both functions rather than assumed to.

What this cannot show is which element each answer reaches;
`test_file_viewer_split.py` reads that, and the pair of files is the whole claim:
`readable` hands markup through untouched, and the `<pre>` it goes into is what
escapes it.

Skipped when node is absent, as `test_theme_resolution.py` skips. Needs no
fastapi (bar the one case that asks the download route for the archive's name),
no network, no Ollama and no rebuilt bundle.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from artifacts.names import ALL_NAMES

from .jsx_sweep import FRONTEND_SRC

VIEWER = FRONTEND_SRC / "components" / "FileViewer.jsx"

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# Where the plain JavaScript ends and the JSX begins, and the imports that have
# to go with it. Both are asserted to have matched, so a rearranged module fails
# here rather than being run as a slice that no longer holds the two functions.
COMPONENT_STARTS = "export default function"
IMPORT_LINE = re.compile(r"^import .*$", re.MULTILINE)
LIFTED = ("function howToShow", "function readable")

# The three answers, spelled as the module spells them. Pinned here so a rename
# fails in one place with a clear message rather than in every row below.
JSON_TEXT = "json"
PLAIN_TEXT = "text"
RENDERED = "html"
REFUSED = None

# Every file a run can leave behind, and how the page shows it. Written out
# rather than derived from the suffix, because a rule that derived the
# expectation the same way the code does would agree with any rule at all.
EXPECTED = {
    "surfaces.json": JSON_TEXT,
    "aibom.json": JSON_TEXT,
    "sbom.json": JSON_TEXT,
    "sbom.cyclonedx.json": JSON_TEXT,
    "mapping.json": JSON_TEXT,
    "findings.json": JSON_TEXT,
    "planner.json": JSON_TEXT,
    "findings.sarif.json": JSON_TEXT,
    "remediation.json": JSON_TEXT,
    "findings.openvex.json": JSON_TEXT,
    "report.md": PLAIN_TEXT,
    "remediation.md": PLAIN_TEXT,
    "report.html": RENDERED,
    "remediation.html": RENDERED,
    "report.pdf": REFUSED,
    "remediation.pdf": REFUSED,
}

# The two whose middle word is not their kind, and the two nobody can read as
# text. Named, because a dictionary comparison passes as one assertion and these
# are the four rows worth failing on their own.
THE_MACHINE_DOCUMENTS = ("findings.sarif.json", "findings.openvex.json")
THE_RENDERED_REPORTS = ("report.pdf", "remediation.pdf")

# Names no run writes, to show the answer comes from the end of the name rather
# than from anywhere in it: a suffix nothing reads, no suffix at all, and a json
# document inside an archive.
NOT_DOCUMENTS = ("sbom.spdx.xml", "LICENSE", "findings.json.zip")

# What `readable` is given and what it must answer. The broken document keeps
# its trailing comma and its comment, which is exactly what makes it broken.
A_JSON_DOCUMENT = '{"app":"demo","findings":[1,2]}'
PRETTY_PRINTED = ('{\n  "app": "demo",\n  "findings": [\n    1,\n    2\n  ]\n}')
BROKEN_JSON = '{\n  "app": "demo",\n  // why this file is like this\n}\n'
MARKUP_IN_A_FINDING = '{"title":"<script>alert(1)</script>"}'


def module_head() -> str:
    """The plain-JavaScript part of the viewer, with its imports dropped."""
    text = VIEWER.read_text(encoding="utf-8")
    assert COMPONENT_STARTS in text, f"{VIEWER.name} declares no component to cut at"
    head, dropped = IMPORT_LINE.subn("", text[: text.index(COMPONENT_STARTS)])
    assert dropped >= 1, f"{VIEWER.name} no longer imports anything; check this lift"
    for name in LIFTED:
        assert name in head, f"the lifted head no longer holds `{name}`"
    return head


def probe(expression: str, given: object, tmp_path: Path) -> object:
    """Evaluate one expression against the viewer's real head, over one argument."""
    script = tmp_path / "file_viewer_probe.mjs"
    script.write_text(module_head()
                      + "\nconst given = JSON.parse(process.argv[2]);\n"
                      f"console.log(JSON.stringify({expression}));\n",
                      encoding="utf-8")
    done = subprocess.run([NODE, str(script), json.dumps(given)],
                          capture_output=True, text=True, check=False)
    assert done.returncode == 0, f"node refused {expression}:\n{done.stderr}"
    return json.loads(done.stdout)


def kinds_of(names: tuple[str, ...], tmp_path: Path) -> dict[str, str | None]:
    """Ask the real `howToShow` how it would show each of these files."""
    answered = probe("given.map(howToShow)", list(names), tmp_path)
    assert len(answered) == len(names), "node answered for a different number of names"
    return dict(zip(names, answered))


def readable(text: str, how: str, tmp_path: Path) -> str:
    """Ask the real `readable` what it would put on the page for these bytes."""
    return probe("readable(given[0], given[1])", [text, how], tmp_path)


# --- the vocabulary, and every file a run writes ------------------------------

def test_the_three_kinds_are_the_names_this_file_pins(tmp_path) -> None:
    """One place for the spelling, so a rename fails here and not in sixteen rows."""
    assert probe("[JSON_TEXT, PLAIN_TEXT, RENDERED]", None,
                 tmp_path) == [JSON_TEXT, PLAIN_TEXT, RENDERED]


def test_every_file_a_run_can_leave_behind_is_accounted_for() -> None:
    """A seventeenth artifact fails here rather than arriving with whatever its suffix means."""
    assert sorted(EXPECTED) == sorted(ALL_NAMES)


def test_every_artifact_is_shown_the_way_this_file_says(tmp_path) -> None:
    """The whole table at once, over the real list rather than a transcription of it."""
    assert kinds_of(tuple(ALL_NAMES), tmp_path) == {name: EXPECTED[name] for name in ALL_NAMES}


def test_both_findings_documents_are_json_whatever_their_middle_word_says(tmp_path) -> None:
    """`findings.sarif.json` and `findings.openvex.json`: a whole-name table is how this breaks."""
    kinds = kinds_of(THE_MACHINE_DOCUMENTS, tmp_path)
    assert kinds == {name: JSON_TEXT for name in THE_MACHINE_DOCUMENTS}


def test_the_two_pdfs_are_refused_rather_than_read_as_text(tmp_path) -> None:
    """Refused by suffix before a byte is fetched: PDF bytes as text are mojibake."""
    assert kinds_of(THE_RENDERED_REPORTS, tmp_path) == {
        name: REFUSED for name in THE_RENDERED_REPORTS}


def test_the_archive_of_the_whole_run_is_refused(tmp_path) -> None:
    """The other thing on the panel, and the download route owns its name."""
    pytest.importorskip("fastapi", reason="the archive's name lives in the download route")
    from downloads import BUNDLE_NAME
    assert kinds_of((BUNDLE_NAME,), tmp_path) == {BUNDLE_NAME: REFUSED}


def test_a_name_that_only_contains_a_readable_suffix_is_refused(tmp_path) -> None:
    """The end of the name decides, not the middle: `findings.json.zip` is an archive."""
    assert kinds_of(NOT_DOCUMENTS, tmp_path) == {name: REFUSED for name in NOT_DOCUMENTS}


# --- and what the bytes look like once they are shown -------------------------

def test_a_json_document_is_pretty_printed(tmp_path) -> None:
    """A 300-byte document on one line is why the viewer exists at all."""
    assert readable(A_JSON_DOCUMENT, JSON_TEXT, tmp_path) == PRETTY_PRINTED


def test_a_json_document_that_will_not_parse_is_returned_byte_for_byte(tmp_path) -> None:
    """The decision, not a fallback: the broken text is the thing a reader needs."""
    assert readable(BROKEN_JSON, JSON_TEXT, tmp_path) == BROKEN_JSON


def test_a_text_file_is_never_reformatted_even_when_it_parses(tmp_path) -> None:
    """`report.md` holding a json fragment is still markdown, and is shown as written."""
    assert readable(A_JSON_DOCUMENT, PLAIN_TEXT, tmp_path) == A_JSON_DOCUMENT


def test_markup_inside_a_finding_is_handed_through_untouched(tmp_path) -> None:
    """Nothing is stripped here; `test_file_viewer_split.py` holds the `<pre>` that escapes it."""
    shown = readable(MARKUP_IN_A_FINDING, JSON_TEXT, tmp_path)
    assert "<script>alert(1)</script>" in shown
    assert json.loads(shown) == json.loads(MARKUP_IN_A_FINDING)
