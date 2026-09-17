"""The verify button: the fields it reads, when it is offered, and what it claims.

Three jobs, and the third is the one a reader of this project should care about.

**The fields.** `KeyVerify.jsx` and `KeyBadge.jsx` bind a grading key under
`keyDocument`, not `key`, so `test_jsx_key_fields.py`'s sweep does not see them
at all. A field JavaScript cannot answer is `undefined` and React renders that
as nothing, so `keyDocument.verified_date` misspelled shows an empty page rather
than an error -- the defect `test_jsx_record_fields.py` was written for, on a
shape nothing else in the page touches.

**The control.** The button exists, and it is disabled while the name is empty.
That is a convenience, not a rule: `run_record.auditor_refusals` is where a name
is really judged, and `test_key_verify_refusals.py` holds the server side. A
disabled button read as the guarantee is exactly how a rule ends up living only
in a browser.

**What it tells the person pressing it.** This is the honest-reporting half of
the whole feature. Recording a check clears `key_unverified` and nothing else --
the key stays `tool_drafted`, so both drafting qualifications go on firing -- and
a page that let a reader believe they were signing the key into independence
would be the failure. So the component is asserted to name all three
qualifications, and the editor is asserted to have stopped claiming, as it did
until 2026-09-16, that a checked draft stays unverified for ever.

**Text, and the file says so.** `jsx_sweep.strip_comments` runs first, so prose
explaining the rule is not read as code. **No test in this suite renders a React
component**; this cannot show that the button is on screen, that the handler is
wired, or that a disabled attribute stops a click. That gap is recorded in
`docs/TODO.md` and is not closed here.
"""

import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")

from .jsx_sweep import FRONTEND_SRC, accessors_in, strip_comments, unknown   # noqa: E402
from .key_fixtures import a_drafted_key                       # noqa: E402

# The name both components bind a grading key under.
KEY_DOCUMENT = "keyDocument"

# The files whose `keyDocument` is a grading key. Named rather than swept over
# the whole tree, for the reason `test_jsx_key_fields.py` narrows `entry`.
KEY_DOCUMENT_FILES = ("KeyVerify.jsx", "KeyBadge.jsx")

COMPONENTS = FRONTEND_SRC / "components"
VERIFY = COMPONENTS / "KeyVerify.jsx"
EDITOR = COMPONENTS / "KeyEditor.jsx"

# A floor under the sweep: one that matched nothing would pass having read
# nothing. Measured today at six across the two files.
MINIMUM_ACCESSORS = 4

# A field no drafted key carries, to show the check reports rather than tolerates.
FIELD_THAT_DOES_NOT_EXIST = "verified_on"

# The three qualifications the component has to be honest about: the one a
# recorded check clears, and the two that survive it.
CLEARED = "key_unverified"
SURVIVING = ("key_ai_drafted", "key_drafted_by_scored_system")

# The button's own disabled expression, and the two things in it: a claim in
# flight, and a name nobody typed.
BUTTON = re.compile(r"<button[^>]*?disabled=\{([^}]*)\}", re.DOTALL)
EMPTY_NAME = "!name.trim()"
IN_FLIGHT = "sending"

# What the editor used to say and may not say again: that a drafted key is
# unverified however much of it a person checks. It was true while
# `harness.check_key` refused the pairing; the verify route is the way out now.
WITHDRAWN_CLAIMS = ("and unverified", "even after a human checks")


def source_of(path: Path) -> str:
    """One component's JSX with its comments stripped, so prose is not read as code."""
    return strip_comments(path.read_text(encoding="utf-8"))


def key_document_accessors() -> list[tuple[str, str]]:
    """Every `keyDocument.field` read in the files that bind a grading key."""
    found: list[tuple[str, str]] = []
    for name in KEY_DOCUMENT_FILES:
        text = (COMPONENTS / name).read_text(encoding="utf-8")
        found += [(name, field) for field in accessors_in(text, KEY_DOCUMENT)]
    return found


def disabled_expression() -> str:
    """What the record button's `disabled` is bound to, insisting there is a button."""
    found = BUTTON.search(source_of(VERIFY))
    assert found, f"{VERIFY.name} has no button with a disabled binding this test can read"
    return found.group(1)


# --- the fields it reads exist -------------------------------------------------

def test_every_key_field_the_verify_button_reads_exists(tmp_path) -> None:
    """`verified`, `verified_by` and `verified_date` are the three it shows as a fact."""
    assert unknown(KEY_DOCUMENT, set(a_drafted_key(tmp_path)),
                   key_document_accessors()) == []


def test_the_sweep_read_something(tmp_path) -> None:
    """Guard: an empty list would satisfy the check above having read nothing."""
    assert len(key_document_accessors()) >= MINIMUM_ACCESSORS


def test_a_field_no_key_answers_is_reported_and_named(tmp_path) -> None:
    """Guard on the check itself: a bad field is named with its file, not passed over."""
    planted = [(VERIFY.name, FIELD_THAT_DOES_NOT_EXIST)]
    assert unknown(KEY_DOCUMENT, set(a_drafted_key(tmp_path)), planted) == [
        f"{VERIFY.name}: {KEY_DOCUMENT}.{FIELD_THAT_DOES_NOT_EXIST}"]


def test_the_three_fields_a_recorded_check_writes_are_all_read() -> None:
    """The route writes three and the page shows three: a claim with no date reads as none."""
    read = {field for _file, field in key_document_accessors()}
    assert {"verified", "verified_by", "verified_date"} <= read


# --- the control ---------------------------------------------------------------

def test_the_button_is_disabled_while_no_name_is_typed() -> None:
    """A check names who made it, so the control that records one is not offered without a name."""
    assert EMPTY_NAME in disabled_expression()


def test_the_button_is_disabled_while_a_claim_is_in_flight() -> None:
    """One check per draft: a second press before the first answers is a refused request."""
    assert IN_FLIGHT in disabled_expression()


def test_the_name_the_button_reads_is_the_one_the_field_writes() -> None:
    """A button guarded on a state nothing sets would be disabled for ever."""
    text = source_of(VERIFY)
    assert "setName(event.target.value)" in text
    assert "value={name}" in text


def test_the_control_is_not_offered_once_a_check_is_recorded() -> None:
    """A second claim is a 400, so the page shows the standing as a fact instead of a form."""
    assert "if (keyDocument.verified) return" in source_of(VERIFY)


def test_the_editor_mounts_the_verify_control() -> None:
    """A component nobody renders is a feature that shipped and cannot be reached."""
    text = source_of(EDITOR)
    assert "<KeyVerify" in text
    assert f"{KEY_DOCUMENT}={{key}}" in text


# --- and what it tells the person pressing it ---------------------------------

def test_the_control_names_the_qualification_it_clears() -> None:
    """The one thing recording a check does, said where a person is about to do it."""
    assert CLEARED in source_of(VERIFY)


@pytest.mark.parametrize("qualification", SURVIVING)
def test_the_control_names_both_qualifications_that_survive_it(qualification: str) -> None:
    """The safety argument, in the browser: a checked draft still is not independent.

    A reader who thinks pressing this signs the key into independence is the
    failure the paragraph exists to prevent, so both strings are named rather
    than summarised as "some warnings remain".
    """
    assert qualification in source_of(VERIFY)


@pytest.mark.parametrize("claim", WITHDRAWN_CLAIMS)
def test_no_page_still_says_a_checked_draft_stays_unverified(claim: str) -> None:
    """The sentence the change made false, gone from every file in the page.

    Read **raw**, comments included, and swept across the whole tree rather than
    aimed at one file. Stripped, a stale comment reasserting it would pass; aimed
    at `KeyEditor.jsx`, a copy of the paragraph moved into another component
    would. A claim about what a reader is told is not made truer by living in a
    comment, because the next person to rewrite the prose reads the comment
    first.
    """
    said = [path.name for path in sorted(FRONTEND_SRC.rglob("*.jsx"))
            if claim in path.read_text(encoding="utf-8")]
    assert said == []


def test_the_sweep_would_have_found_the_claim(tmp_path) -> None:
    """Guard on the two above: a glob matching no file passes every absence check.

    The tree really is read, and it really holds the components this file is
    about -- otherwise "the claim is nowhere" would be a statement about an
    empty list of files.
    """
    swept = {path.name for path in FRONTEND_SRC.rglob("*.jsx")}
    assert {VERIFY.name, EDITOR.name} <= swept


def test_the_editor_still_says_the_source_does_not_move() -> None:
    """The half that is still true, kept: without this the test above passes on an empty file."""
    text = source_of(EDITOR)
    assert "who chose them" in text
    assert "{key.source}" in text
