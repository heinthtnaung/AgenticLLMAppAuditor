"""A key the scored system wrote carries both warnings, and can never be signed off.

`tool_drafted` is the narrower and worse case of `ai_drafted`, so it earns
`key_drafted_by_scored_system` **on top of** `key_ai_drafted` rather than
instead of it. That distinction is the whole test: every reader, every table
and every sentence in the write-up that keys on `key_ai_drafted` would stop
firing on the worst key this project can produce if the new string replaced the
old one, and the replacement would look like a passing test suite.

The second half is the refusal. `key_drafted_by_scored_system` is about
validity, not quality: it survives a human checking every entry, because
checking cannot make the tool's own choice of what to include independent. So
`harness.check_key` refuses `tool_drafted` with `verified: true` outright,
rather than letting a well-meaning reviewer erase the qualification by ticking
a box.
"""

import pytest

from evaluation.harness import check_key
from evaluation.scorer import QUALIFICATIONS, score_app
from evaluation_fixtures import (
    APP,
    findings_document,
    grading_key,
    key_entry,
    surfaces_document,
)
from grading_keys import (
    AI_DRAFTED, DRAFTED_SOURCES, GROUND_TRUTH_SUFFIX, MANUAL_REVIEW,
    TOOL_DRAFTED, key_path)
from key_drafting import DRAFTED_KEYS_DIR

# The two strings a drafted key's figures travel with, and the one the worse
# case adds. Spelled here so a rename in `scorer.py` fails this file loudly.
AI_DRAFTED_QUALIFICATION = "key_ai_drafted"
SCORED_SYSTEM_QUALIFICATION = "key_drafted_by_scored_system"

# Where a refused key would have been read from. Only the message uses it, so
# it is built from the constant the drafter writes to rather than respelled.
KEY_PATH = key_path(APP, GROUND_TRUTH_SUFFIX, DRAFTED_KEYS_DIR)

# A source no vocabulary knows, shaped like a plausible typo of a real one.
MISSPELLED_SOURCE = "tool-drafted"


def qualifications(source: str, verified: bool = False) -> list[str]:
    """Score one app against a key from a named source, and return what bounds its numbers."""
    key = grading_key([key_entry()], source=source, verified=verified)
    return score_app(APP, key, findings_document(), surfaces_document())["qualifications"]


def checkable(source: str = TOOL_DRAFTED, verified: bool = False) -> dict:
    """A key in the shape `check_key` reads, defaulting to an unverified drafted one."""
    return grading_key([key_entry()], source=source, verified=verified)


# --- the two qualifications, and their order ----------------------------------

def test_a_tool_drafted_key_earns_the_general_warning_too() -> None:
    """The point of the whole file: the narrower string is additive, never a substitute."""
    said = qualifications(TOOL_DRAFTED)
    assert AI_DRAFTED_QUALIFICATION in said
    assert SCORED_SYSTEM_QUALIFICATION in said


def test_an_ai_drafted_key_earns_only_the_general_warning() -> None:
    """The off position: a model that is not the scored system is a different, milder problem."""
    said = qualifications(AI_DRAFTED)
    assert AI_DRAFTED_QUALIFICATION in said
    assert SCORED_SYSTEM_QUALIFICATION not in said


def test_a_hand_reviewed_key_earns_neither() -> None:
    """`source` is read, not assumed: a human-written key carries no drafting warning at all."""
    said = qualifications(MANUAL_REVIEW, verified=True)
    assert [name for name in (AI_DRAFTED_QUALIFICATION, SCORED_SYSTEM_QUALIFICATION)
            if name in said] == []


def test_both_strings_are_in_the_published_vocabulary() -> None:
    """The write-up quotes these verbatim, so neither may be a string only this file knows."""
    assert AI_DRAFTED_QUALIFICATION in QUALIFICATIONS
    assert SCORED_SYSTEM_QUALIFICATION in QUALIFICATIONS


def test_the_general_warning_is_earned_from_the_shared_source_list() -> None:
    """Guard: `key_ai_drafted` comes from `DRAFTED_SOURCES`, which must hold both sources."""
    assert set(DRAFTED_SOURCES) == {AI_DRAFTED, TOOL_DRAFTED}


# --- a tool may not verify its own key ----------------------------------------

def test_a_tool_drafted_key_that_claims_verification_is_refused() -> None:
    """Ticking `verified` would erase `key_unverified` and leave the circularity unsaid."""
    with pytest.raises(ValueError, match="cannot verify the key it"):
        check_key(checkable(verified=True), KEY_PATH)


def test_the_same_key_unverified_is_accepted() -> None:
    """The off position: the refusal is about the pair of fields, not about the source."""
    assert check_key(checkable(), KEY_PATH)["source"] == TOOL_DRAFTED


def test_a_key_a_human_took_over_may_be_verified_once_its_source_says_so() -> None:
    """The message names the way out, so the refusal is a rule and not a dead end."""
    assert check_key(grading_key([key_entry()], source=MANUAL_REVIEW, verified=True),
                      KEY_PATH)["verified"] is True


# --- a source outside the vocabulary ------------------------------------------

def test_a_source_outside_the_vocabulary_is_refused() -> None:
    """A typo used to be accepted and earn no qualification at all -- silence where it matters."""
    with pytest.raises(ValueError, match="not one of"):
        check_key(checkable(source=MISSPELLED_SOURCE), KEY_PATH)


def test_the_refused_source_would_otherwise_have_earned_nothing() -> None:
    """Why the refusal exists: the scorer compares by value, so a typo silently drops both."""
    said = qualifications(MISSPELLED_SOURCE)
    assert [name for name in (AI_DRAFTED_QUALIFICATION, SCORED_SYSTEM_QUALIFICATION)
            if name in said] == []
