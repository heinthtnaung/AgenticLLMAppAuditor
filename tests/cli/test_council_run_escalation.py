"""Guards on the audit's escalation: none unless a model is named, and only what was left open.

Why an escalated reply settles a metric, or does not, is `chairman.rule_on_escalation`.
"""

import io
import json

import pytest

from cli.council_run import assessments, build_roster, escalation_member, watching
from council.prompt import PROMPT_VERSION, REVERSED_PROMPT_VERSION
from council.ruling import Basis
from findings.finding import build_finding
from report.council_record import CouncilAssessment, CouncilWithoutVector
from cli_samples import ADVISORY, LEGAL, LODASH, QUOTATION

FINDING = build_finding(LODASH, ADVISORY)
COUNCIL = build_roster(("small", "other"))
BIG = "big:27b"


def answering(asked: list, big_reads_s: bool = True):
    """Answer every metric for the council but S, which it declines and the escalation reads."""

    def said(member, prompt):
        """Note the call, then answer it: a decline on S unless the escalation model reads it."""
        asked.append((member.name, prompt.metric, prompt.version))
        if prompt.metric == "S" and not (member.name == BIG and big_reads_s):
            return json.dumps({"value": "NO_EVIDENCE", "evidence": ""})
        value = LEGAL[prompt.metric]
        return json.dumps({"value": value, "evidence": QUOTATION, "confidence": "high"})

    return {"ollama": said}


def test_the_escalation_model_is_a_local_member_on_this_machine_and_none_is_none():
    big = escalation_member(BIG)
    assert (big.name, big.model, big.provider, big.family, big.runs_local) == (
        BIG, BIG, "ollama", "big", True,
    )
    assert escalation_member(None) is None


def test_with_no_escalation_model_nothing_is_escalated_and_no_extra_call_is_made():
    asked = []
    (outcome,) = assessments((FINDING,), COUNCIL, answering(asked), escalation=None)
    assert len(asked) == 2 * 8 * 2
    assert {name for name, *_ in asked} == {"small", "other"}
    assert isinstance(outcome, CouncilWithoutVector)
    assert [one.escalation for one in outcome.rulings] == [None] * 8


def test_only_the_open_metric_goes_to_the_escalation_model_both_ways_after_the_council():
    asked = []
    assessments((FINDING,), COUNCIL, answering(asked), escalation=escalation_member(BIG))
    assert asked[-2:] == [(BIG, "S", PROMPT_VERSION), (BIG, "S", REVERSED_PROMPT_VERSION)]
    assert [name for name, *_ in asked].count(BIG) == 2


def test_an_escalation_that_settles_the_last_open_metric_hands_over_a_vector():
    (outcome,) = assessments((FINDING,), COUNCIL, answering([]), escalation=escalation_member(BIG))
    assert isinstance(outcome, CouncilAssessment)
    (s,) = [one for one in outcome.rulings if one.metric == "S"]
    settled = (s.value, s.basis, s.escalation.prior.value)
    assert settled == ("U", Basis.ESCALATED.value, "unresolved")


def test_an_escalation_that_settles_nothing_leaves_the_metric_open_and_recorded():
    escalation = escalation_member(BIG)
    clients = answering([], big_reads_s=False)
    (outcome,) = assessments((FINDING,), COUNCIL, clients, escalation=escalation)
    assert isinstance(outcome, CouncilWithoutVector)
    assert outcome.unresolved_metrics == ("S",)
    (s,) = [one for one in outcome.rulings if one.metric == "S"]
    assert s.escalation.said.kind.value == "declined"


def test_an_escalation_model_on_the_council_is_refused_before_any_call():
    asked = []
    with pytest.raises(ValueError, match="small is on the council"):
        assessments((FINDING,), COUNCIL, answering(asked), escalation=escalation_member("small"))
    assert asked == []


def test_an_escalation_call_is_said_on_its_own_line_and_the_council_s_total_is_unchanged():
    out = io.StringIO()
    progress = watching((FINDING,), COUNCIL, out)
    assessments((FINDING,), COUNCIL, answering([]), progress, escalation=escalation_member(BIG))
    lines = out.getvalue().splitlines()
    assert lines[31].startswith("council 32/32  ")
    assert lines[32:] == [
        f"escalation 1  finding 1/1 {FINDING.advisory.advisory_id}  S  {BIG}",
        f"escalation 2  finding 1/1 {FINDING.advisory.advisory_id}  S (options reversed)  {BIG}",
    ]
