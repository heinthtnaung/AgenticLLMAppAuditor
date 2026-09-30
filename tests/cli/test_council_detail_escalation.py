"""Guards on an escalation in the record: what the council left it as, and what it cross-checked.

A vector every metric of which rests on one quotation is marked nothing
cross-checked. An escalation from an unresolved metric adds one quotation where
there was none; one from a contest sides with a value a member's verified
quotation already supports, so two stand behind it.
"""

import json

from cli.council_run import assessments, build_roster, escalation_member
from cli_samples import ADVISORY, LEGAL, LODASH, QUOTATION
from findings.finding import build_finding
from report.council_record import CouncilAssessment, Outcome, SaidKind

FINDING = build_finding(LODASH, ADVISORY)
COUNCIL = build_roster(("small", "other"))
BIG = escalation_member("big:27b")
# What the escalation model reads, each quoting the advisory.
ESCALATION_READS = {"AV": "L", "S": "U"}


def value_read(name: str, metric: str, small_declines: set[str], other_reads: dict) -> str | None:
    """Give the value one model reads for a metric, or None where it declines."""
    if name == BIG.name:
        return ESCALATION_READS.get(metric)
    if name == "other":
        return other_reads.get(metric)
    return None if metric in small_declines else LEGAL[metric]


def answering(small_declines: set[str], other_reads: dict[str, str]):
    """Give a council where `small` quotes all but some metrics, `other` only those it reads."""

    def said(member, prompt):
        """Quote the advisory for the value this model reads, or decline."""
        value = value_read(member.name, prompt.metric, small_declines, other_reads)
        if value is None:
            return json.dumps({"value": "NO_EVIDENCE", "evidence": ""})
        return json.dumps({"value": value, "evidence": QUOTATION, "confidence": "high"})

    return {"ollama": said}


def assessed(small_declines: set[str], other_reads: dict[str, str]) -> CouncilAssessment:
    """Put the sample finding to the council, escalating what it leaves open."""
    clients = answering(small_declines, other_reads)
    (outcome,) = assessments((FINDING,), COUNCIL, clients, escalation=BIG)
    assert isinstance(outcome, CouncilAssessment)
    return outcome


def test_an_unresolved_metric_the_escalation_settled_rests_on_its_quotation_alone():
    # `small` quotes seven metrics alone and declines S, which only the escalation reads.
    outcome = assessed(small_declines={"S"}, other_reads={})
    assert outcome.nothing_cross_checked is True


def test_a_contest_the_escalation_settled_rests_on_two_quotations():
    # `small` quotes every metric alone but AV, where `other` quotes L against its N.
    outcome = assessed(small_declines=set(), other_reads={"AV": "L"})
    assert outcome.nothing_cross_checked is False


def test_the_record_keeps_what_the_council_left_the_metric_as_and_what_the_model_said():
    outcome = assessed(small_declines=set(), other_reads={"AV": "L"})
    (av,) = [one for one in outcome.rulings if one.metric == "AV"]
    assert (av.outcome, av.value, av.escalation.prior) == (Outcome.SETTLED, "L", Outcome.CONTESTED)
    assert (av.escalation.said.kind, av.escalation.said.verified) == (SaidKind.ANSWERED, True)
    assert av.escalation.said.member.reversed_prompt_version
