"""Guards on reading the approval rule off a record: each finding paired with its own risk."""

from approval_runs import DISPUTED, EXPOSED, QUIET, SEVERE, UNEXPOSED, approval_report
from organisation.approval_rule import ApprovalReason
from report.approval_needed import needing_approval, reasons_for


def test_a_record_with_no_answers_marks_only_the_findings_whose_sources_disagree():
    assert needing_approval(approval_report()) == (DISPUTED,)


def test_a_weighed_record_marks_both_halves_in_the_records_own_order():
    assert needing_approval(approval_report(EXPOSED)) == (DISPUTED, SEVERE)


def test_each_finding_is_given_the_reasons_its_own_risk_score_meets():
    report = approval_report(EXPOSED)
    assert reasons_for(report, SEVERE) == (ApprovalReason.RISK_BAND,)
    assert reasons_for(report, QUIET) == ()


def test_an_environment_that_puts_nothing_high_leaves_only_the_disagreement():
    assert needing_approval(approval_report(UNEXPOSED)) == (DISPUTED,)
