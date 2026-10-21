"""Guards on the approval badge both renderings share: one word and tone per decision.

A flagged finding shows "needs approval" only when the audit records no approval;
a recorded approval turns it into the decision a human made, each in its own tone,
so the badge beside a finding cannot say the opposite of the approval box above it.
"""

from organisation.approval import Approval, Decision, NotApproved
from report.html_approval import DECISION_BADGES, UNAPPROVED_BADGE, approval_status

INSTANT = "2026-09-23T09:15:00Z"


def test_no_recorded_approval_is_the_needs_approval_alarm():
    assert approval_status(NotApproved("nobody looked")) == ("needs approval", "alarm")
    assert UNAPPROVED_BADGE == ("needs approval", "alarm")


def test_an_approved_audit_turns_a_flag_into_the_ok_approved_badge():
    assert approval_status(Approval("hein", Decision.APPROVED, INSTANT)) == ("approved", "ok")


def test_an_overridden_audit_gets_a_word_and_tone_distinct_from_approved():
    overridden = approval_status(Approval("hein", Decision.OVERRIDDEN, INSTANT))
    assert overridden == ("overridden", "warn")
    assert overridden != approval_status(Approval("hein", Decision.APPROVED, INSTANT))


def test_every_decision_has_a_badge_so_a_new_one_cannot_render_unmapped():
    # A Decision added without a badge would raise at render; this keeps that gap
    # red here, where it names the decision rather than crashing a rendered page.
    assert set(DECISION_BADGES) == set(Decision)
