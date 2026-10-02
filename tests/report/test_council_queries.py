"""Guards on the report-side queries over a council's record: what it left open, ran on, and flagged.

These read the projection and decide nothing new, so a change here is a change to
what the renderers that share them are shown, not to the record itself.
"""

from cli.council_run import SOURCES_AGREE
from council_runs import DISSENTING, OPEN_TWO_WAYS, council_ran
from escalation_runs import SETTLING, UNSTABLE_AND_INVENTED, by_metric, escalated
from report.council_queries import council_left_open, flagged_metrics, was_assessed
from report.council_record import CouncilAssessment, CouncilNotAsked, CouncilWithoutVector, Outcome
from same_evidence_runs import same_words, unflagged


def test_a_settled_metric_the_council_did_not_escalate_was_not_left_open():
    settled = by_metric(council_ran())["AV"]
    assert (settled.outcome, settled.escalation) == (Outcome.SETTLED, None)
    assert council_left_open(settled) is False


def test_a_contested_metric_the_council_could_not_settle_was_left_open():
    contested = by_metric(council_ran(**DISSENTING))["AV"]
    assert (contested.outcome, contested.escalation) == (Outcome.CONTESTED, None)
    assert council_left_open(contested) is True


def test_an_unresolved_metric_the_council_could_not_settle_was_left_open():
    unresolved = by_metric(council_ran(**OPEN_TWO_WAYS))["S"]
    assert (unresolved.outcome, unresolved.escalation) == (Outcome.UNRESOLVED, None)
    assert council_left_open(unresolved) is True


def test_a_metric_the_escalation_settled_was_still_left_open_by_the_council():
    escalated_settled = by_metric(escalated(SETTLING))["AC"]
    assert escalated_settled.outcome is Outcome.SETTLED
    assert escalated_settled.escalation is not None
    assert council_left_open(escalated_settled) is True


def test_a_metric_the_escalation_could_not_settle_was_left_open():
    escalated_open = by_metric(escalated(UNSTABLE_AND_INVENTED))["AC"]
    assert escalated_open.outcome is Outcome.CONTESTED
    assert escalated_open.escalation is not None
    assert council_left_open(escalated_open) is True


def test_a_finding_passed_over_is_not_a_finding_that_was_assessed():
    settled, still_open = council_ran(), council_ran(**DISSENTING)
    assert (type(settled), type(still_open)) == (CouncilAssessment, CouncilWithoutVector)
    assert was_assessed(CouncilNotAsked("CVE-1", SOURCES_AGREE)) is False
    assert was_assessed(settled) is True
    assert was_assessed(still_open) is True


def test_flagged_metrics_names_only_the_rulings_read_two_ways_from_the_same_words():
    assert flagged_metrics(same_words()) == ("AV",)
    assert flagged_metrics(unflagged(same_words())) == ()
    assert flagged_metrics(CouncilNotAsked("CVE-1", "the sources agreed")) == ()
