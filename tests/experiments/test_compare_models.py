"""Does the study refuse a document that does not add up, and say what it found?

Two things are checked here, and neither runs a model. `compare()` itself is not
called: it would open a socket to Ollama and to a hosted provider, which is the
whole reason the study is not part of the tool. What is called is the pair of
pure functions around it -- the guard that every subject lands in exactly one
bucket, and the line the report leads with.

The sentence matters as much as the guard. A dangling string literal once cut
the agreed note off at "Agreement is not proof of ", so the published page
carried half a caveat. Each assertion below ends on a full stop for that reason.
"""

import pytest
from .arm_fixtures import (
    CLEARED_STATE, FIRST, FLAGGED_STATE, HOSTED, LOCAL, MODEL_UNREACHABLE_STATE, SECOND,
    arm, study_result)
from compare_models import BUCKETS, SCHEMA_VERSION, _check_partition, _note

# The end of the agreed note, which a dangling string literal used to swallow.
AGREED_ENDING = "same way."
TRUNCATED_ENDING = "Agreement is not proof of "

# The opening of the note for a run that compared nothing at all.
NO_COMPARISON_OPENING = "**No template was put to a model, so nothing here compares them.**"


def agreed_result() -> dict:
    """A comparison where both models were asked and said the same thing."""
    return study_result([arm(LOCAL, {FIRST: FLAGGED_STATE}),
                         arm(HOSTED, {FIRST: FLAGGED_STATE})])


def test_the_guard_accepts_a_document_whose_buckets_add_up() -> None:
    """Non-vacuity: a real partition passes, so the failure below is about the numbers."""
    result = agreed_result()
    assert result["subjects_seen"] == 1
    assert sum(len(result[bucket]) for bucket in BUCKETS) == 1
    _check_partition(result)


def test_the_guard_refuses_a_document_that_lost_a_subject() -> None:
    """A bucket silently dropping a subject is an error, not a smaller published number."""
    result = agreed_result()
    result["agreements"] = []
    with pytest.raises(ValueError) as raised:
        _check_partition(result)
    assert "sorted 0 subjects but saw 1" in str(raised.value)


def test_the_guard_refuses_a_document_that_counted_a_subject_twice() -> None:
    """The other direction: more sorted than seen is just as wrong."""
    result = agreed_result()
    result["disagreements"] = [{"subject": FIRST, "verdicts": {}}]
    with pytest.raises(ValueError) as raised:
        _check_partition(result)
    assert "sorted 2 subjects but saw 1" in str(raised.value)


def test_the_agreed_note_is_one_complete_sentence() -> None:
    """The caveat is published whole: agreement is not proof, both could be wrong."""
    note = _note(agreed_result())
    assert note.endswith(AGREED_ENDING)
    assert note != TRUNCATED_ENDING
    assert "Agreement is not proof of correctness" in note


def test_the_note_says_nothing_was_compared_when_nothing_was() -> None:
    """Both buckets empty: the run consulted nobody and the note has to say so."""
    unreachable = [arm(LOCAL, {FIRST: MODEL_UNREACHABLE_STATE}),
                   arm(HOSTED, {FIRST: MODEL_UNREACHABLE_STATE})]
    result = study_result(unreachable)
    assert result["agreements"] == [] and result["disagreements"] == []
    note = _note(result)
    assert note.startswith(NO_COMPARISON_OPENING)
    assert note.endswith("This run says nothing about either model.")


def test_the_note_leads_with_the_disagreement_when_there_is_one() -> None:
    """A disagreement is the one real result, so it outranks the agreed wording."""
    result = study_result([arm(LOCAL, {FIRST: FLAGGED_STATE, SECOND: FLAGGED_STATE}),
                           arm(HOSTED, {FIRST: FLAGGED_STATE, SECOND: CLEARED_STATE})])
    note = _note(result)
    assert note.startswith("**They disagree, so at most one is right.**")
    assert AGREED_ENDING not in note


def test_the_document_declares_which_shape_it_is() -> None:
    """Two incompatible files sit in `experiments/results/`; the version tells them apart."""
    assert SCHEMA_VERSION == 1
    assert agreed_result()["schema_version"] == SCHEMA_VERSION
