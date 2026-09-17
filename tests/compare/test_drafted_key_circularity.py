"""A key the scored system wrote carries both warnings, and verifying it clears neither.

`tool_drafted` is the narrower and worse case of `ai_drafted`, so it earns
`key_drafted_by_scored_system` **on top of** `key_ai_drafted` rather than
instead of it. That distinction is the first half of this file: every reader,
every table and every sentence in the write-up that keys on `key_ai_drafted`
would stop firing on the worst key this project can produce if the new string
replaced the old one, and the replacement would look like a passing test suite.

The second half used to be a refusal. `harness.check_key` raised on
`tool_drafted` with `verified: true`, on the reasoning that a tool cannot verify
the key it wrote for itself -- and that conflated two different facts. Who
*chose* the entries is `source`; whether a human has *read* them is `verified`.
The refusal left someone who had checked every entry with no way to say so
except by editing `source`, which erases `key_drafted_by_scored_system`: losing
the warning that matters in order to record a weaker one. Since 2026-09-16 the
pairing is a legal document and the guard is gone.

**What replaces it is the stronger claim, and it is the whole safety argument
for allowing the pairing.** Verifying a drafted key clears `key_unverified` and
*nothing else*, so both drafting qualifications go on firing and a verified
drafted key can never read as an independent measurement. Two shapes of that are
asserted below: the exact set each row of `docs/SCHEMAS.md`'s table earns, and
the exact difference between the verified and unverified runs -- which is where
"and nothing else" is actually held, since it would fail on verification
clearing or adding any qualification at all, key-derived or not.

No filesystem: `check_key` is handed a path only for its messages, and the
scorer is pure.
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
from keys.grading_keys import (
    AI_DRAFTED, DRAFTED_SOURCES, GROUND_TRUTH_SUFFIX, MANUAL_REVIEW,
    TOOL_DRAFTED, key_path)
from keys.key_drafting import DRAFTED_KEYS_DIR

# The two strings a drafted key's figures travel with, and the one the worse
# case adds. Spelled here so a rename in `scorer.py` fails this file loudly.
AI_DRAFTED_QUALIFICATION = "key_ai_drafted"
SCORED_SYSTEM_QUALIFICATION = "key_drafted_by_scored_system"
UNVERIFIED_QUALIFICATION = "key_unverified"

# The three a key's own `source` and `verified` earn, and the only three the
# table below is about. Everything else the scorer attaches -- `small_sample`,
# `model_disabled` -- is a fact about the artifacts, not about the key.
STANDING_QUALIFICATIONS = (AI_DRAFTED_QUALIFICATION, SCORED_SYSTEM_QUALIFICATION,
                           UNVERIFIED_QUALIFICATION)

# Where a refused key would have been read from. Only the message uses it, so
# it is built from the constant the drafter writes to rather than respelled.
KEY_PATH = key_path(APP, GROUND_TRUTH_SUFFIX, DRAFTED_KEYS_DIR)

# A source no vocabulary knows, shaped like a plausible typo of a real one.
MISSPELLED_SOURCE = "tool-drafted"


def qualifications(source: str, verified: bool = False) -> list[str]:
    """Score one app against a key from a named source, and return what bounds its numbers."""
    key = grading_key([key_entry()], source=source, verified=verified)
    return score_app(APP, key, findings_document(), surfaces_document())["qualifications"]


def standing(source: str, verified: bool = False) -> list[str]:
    """Just the qualifications that key's `source` and `verified` earned, sorted."""
    said = qualifications(source, verified)
    return sorted(name for name in STANDING_QUALIFICATIONS if name in said)


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
    """`source` is read, not assumed: a human-written key carries no drafting warning at all.

    Also why editing `source` is the *wrong* way to record a check: it does not
    add a fact about who read the entries, it removes two facts about who chose
    them. The verify route exists so nobody has to make that trade.
    """
    assert standing(MANUAL_REVIEW, verified=True) == []


def test_both_strings_are_in_the_published_vocabulary() -> None:
    """The write-up quotes these verbatim, so neither may be a string only this file knows."""
    assert AI_DRAFTED_QUALIFICATION in QUALIFICATIONS
    assert SCORED_SYSTEM_QUALIFICATION in QUALIFICATIONS
    assert UNVERIFIED_QUALIFICATION in QUALIFICATIONS


def test_the_general_warning_is_earned_from_the_shared_source_list() -> None:
    """Guard: `key_ai_drafted` comes from `DRAFTED_SOURCES`, which must hold both sources."""
    assert set(DRAFTED_SOURCES) == {AI_DRAFTED, TOOL_DRAFTED}


# --- a drafted key a human has checked -----------------------------------------

def test_a_tool_drafted_key_that_claims_verification_is_accepted() -> None:
    """The inversion: the pairing is a legal document, so somebody who checked it can say so."""
    checked = check_key(checkable(verified=True), KEY_PATH)
    assert checked["source"] == TOOL_DRAFTED
    assert checked["verified"] is True


def test_the_same_key_unverified_is_accepted_too() -> None:
    """The off position: neither value of `verified` is refused, so the pair is orthogonal."""
    assert check_key(checkable(), KEY_PATH)["source"] == TOOL_DRAFTED


def test_verifying_a_drafted_key_leaves_both_drafting_warnings_firing() -> None:
    """The safety argument in one line: a checked draft still cannot read as independent."""
    said = qualifications(TOOL_DRAFTED, verified=True)
    assert AI_DRAFTED_QUALIFICATION in said
    assert SCORED_SYSTEM_QUALIFICATION in said


def test_verifying_a_drafted_key_clears_the_unverified_warning() -> None:
    """The one thing it is for: without this the button would record a claim nothing reads."""
    assert UNVERIFIED_QUALIFICATION not in qualifications(TOOL_DRAFTED, verified=True)
    assert UNVERIFIED_QUALIFICATION in qualifications(TOOL_DRAFTED)


def test_an_unverified_drafted_key_earns_exactly_the_three() -> None:
    """The first row of `docs/SCHEMAS.md`'s table, as an equality rather than a membership."""
    assert standing(TOOL_DRAFTED) == sorted(STANDING_QUALIFICATIONS)


def test_a_verified_drafted_key_earns_exactly_the_two() -> None:
    """The second row. Stated as an equality, so a third warning appearing fails here."""
    assert standing(TOOL_DRAFTED, verified=True) == sorted(
        [AI_DRAFTED_QUALIFICATION, SCORED_SYSTEM_QUALIFICATION])


def test_verifying_changes_that_one_qualification_and_no_other() -> None:
    """Where "and nothing else" is really held: the whole list, both directions.

    Compared over every qualification the scorer attaches and not just the three
    a key earns, because the claim is about the act of verifying and not about
    which strings this file happens to know the names of.
    """
    unverified = set(qualifications(TOOL_DRAFTED))
    verified = set(qualifications(TOOL_DRAFTED, verified=True))
    assert unverified - verified == {UNVERIFIED_QUALIFICATION}
    assert verified - unverified == set()


def test_a_hand_written_key_is_verified_without_earning_anything() -> None:
    """The third row of the table: `manual_review` + `verified` is the unqualified case.

    Kept beside the drafted rows because it is what they are measured against --
    the point of the pairing being legal is that a checked draft records the
    same *reading* as this key while keeping two warnings this one never had.
    """
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
