"""Guards on the approval record: a human act, kept so somebody can be held to it."""

import pytest

from organisation.approval import Approval, Decision, NotApproved, read_decision

WHEN = "2026-09-23T09:14:00Z"


def approval(**overrides) -> Approval:
    """Build one approval, changed where a test needs it."""
    fields = {"approver": "someone@example.com", "decision": Decision.APPROVED, "recorded_at": WHEN}
    fields.update(overrides)
    return Approval(**fields)


def test_an_approval_keeps_who_what_and_when():
    recorded = approval(note="reviewed with the platform team")
    assert recorded.approver == "someone@example.com"
    assert recorded.decision is Decision.APPROVED
    assert recorded.recorded_at == WHEN
    assert recorded.note == "reviewed with the platform team"


def test_an_override_is_a_different_decision_from_an_approval():
    assert Decision.OVERRIDDEN is not Decision.APPROVED
    assert read_decision("overridden") is Decision.OVERRIDDEN


@pytest.mark.parametrize("word", ["Approved", " approved ", "APPROVED"])
def test_the_word_is_read_however_an_operator_spelled_it(word):
    assert read_decision(word) is Decision.APPROVED


@pytest.mark.parametrize("word", ["", "maybe", "signed off"])
def test_a_decision_nobody_offers_is_refused(word):
    with pytest.raises(ValueError, match="is not a decision"):
        read_decision(word)


def test_an_approval_nobody_signed_is_refused():
    with pytest.raises(ValueError, match="must name who made it"):
        approval(approver="")


def test_an_approval_that_is_not_a_real_decision_is_refused():
    with pytest.raises(TypeError, match="approved or overridden"):
        approval(decision="approved")


def test_an_approval_with_no_time_is_refused():
    with pytest.raises(ValueError, match="must say when it was made"):
        approval(recorded_at="")


@pytest.mark.parametrize("when", ["yesterday", "2026-13-01", "soon"])
def test_a_time_that_is_not_an_instant_is_refused(when):
    # A record that says "yesterday" is not a record of when anything happened.
    with pytest.raises(ValueError, match="is not an ISO 8601 instant"):
        approval(recorded_at=when)


@pytest.mark.parametrize("when", ["2026-09-23T09:14:00Z", "2026-09-23T09:14:00+00:00"])
def test_a_real_instant_is_accepted_however_it_is_spelled(when):
    assert approval(recorded_at=when).recorded_at == when


def test_nobody_having_approved_is_its_own_record_and_must_say_why():
    assert NotApproved("nothing captured one").reason
    with pytest.raises(ValueError, match="must say why it is absent"):
        NotApproved("")


def test_an_absent_approval_is_not_an_approval():
    assert not isinstance(NotApproved("none given"), Approval)
