"""Guards on escalation: an open metric settles only on a stable, verified, admissible reply."""

import pytest

from council.answer import (
    Confidence,
    MemberAnswer,
    MemberFoundNoEvidence,
    MemberGuessed,
    MemberOrderSensitive,
)
from council.chairman import rule_on_escalation
from council.ruling import (
    Basis, ContestedMetric, NoFallbackPublished, SettledMetric, UnresolvedMetric,
)
from council.run import MemberFailure
from council_samples import ADVISORY, NETWORK_QUOTATION, NOT_IN_THE_ADVISORY, answer, identity

# The escalation model as a reconciled reply names it: asked in both orders.
ESCALATION = identity("big-local", reversed_prompt_version="sample-reversed-version")
CONTESTED = ContestedMetric(metric="AV", candidates=(answer(value="N", name="one"),
                                                   answer(value="L", name="two")))
UNRESOLVED = UnresolvedMetric(metric="AV", fallback=NoFallbackPublished(reason="none offered"))


def escalated(value: str = "N", evidence: str = NETWORK_QUOTATION, member=ESCALATION):
    """Give the escalation model's reconciled answer to AV."""
    return MemberAnswer(
        metric="AV", value=value, evidence=evidence, confidence=Confidence.MEDIUM, member=member
    )


@pytest.mark.parametrize("prior", [CONTESTED, UNRESOLVED], ids=["contested", "unresolved"])
def test_an_order_stable_verified_reply_settles_an_open_metric_on_the_escalated_basis(prior):
    reply = escalated("N")
    ruling = rule_on_escalation(prior, reply, ADVISORY)
    assert ruling == SettledMetric(
        metric="AV", value="N", confidence=Confidence.MEDIUM, basis=Basis.ESCALATED,
        supporting=(reply,),
    )


def test_on_a_contested_metric_only_a_contested_value_settles_it():
    assert rule_on_escalation(CONTESTED, escalated("P"), ADVISORY) is CONTESTED


def test_on_an_unresolved_metric_any_value_the_metric_allows_settles_it():
    assert rule_on_escalation(UNRESOLVED, escalated("P"), ADVISORY).value == "P"


@pytest.mark.parametrize("prior", [CONTESTED, UNRESOLVED], ids=["contested", "unresolved"])
@pytest.mark.parametrize(
    "reply",
    [
        escalated(evidence=NOT_IN_THE_ADVISORY),
        MemberFoundNoEvidence(metric="AV", member=ESCALATION),
        MemberGuessed(metric="AV", value="N", member=ESCALATION),
        MemberOrderSensitive(
            metric="AV", in_order_value="N", reversed_value="L", member=ESCALATION
        ),
        MemberFailure(member=ESCALATION, metric="AV", reason="timed out after 180 s"),
    ],
    ids=["quotation not in the advisory", "declined", "guessed", "order-sensitive", "failed"],
)
def test_anything_else_leaves_the_metric_as_the_council_left_it(prior, reply):
    assert rule_on_escalation(prior, reply, ADVISORY) is prior


def test_a_settled_metric_is_never_escalated():
    settled = SettledMetric(
        metric="AV", value="N", confidence=Confidence.HIGH, basis=Basis.SOLE, supporting=(answer(),)
    )
    with pytest.raises(ValueError, match="AV is settled"):
        rule_on_escalation(settled, escalated("L"), ADVISORY)


def test_a_reply_about_another_metric_is_refused():
    other = MemberFoundNoEvidence(metric="AC", member=ESCALATION)
    with pytest.raises(ValueError, match="AC answered where AV was escalated"):
        rule_on_escalation(CONTESTED, other, ADVISORY)


def test_a_reply_asked_in_one_order_cannot_settle_anything():
    one_order = escalated("N", member=identity("big-local"))
    with pytest.raises(ValueError, match="escalated in one order"):
        rule_on_escalation(UNRESOLVED, one_order, ADVISORY)
