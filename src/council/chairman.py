"""Reconciling n members' answers into one ruling per metric, and then into a vector.

**Nothing here counts members towards a ruling.** `docs/COUNCIL.md` forbids a
majority vote at any n, because members built on one base model share its
mistakes, so four answers are four pieces of evidence and not four votes. What
decides is whether the quotation verifies: an answer whose evidence is not in the
advisory supports nothing, however many members give it.

That makes the design's first two rules one computation. Among the answers whose
quotation verified, either they support one value -- settled -- or they do not,
and the metric is contested, which the escalation model may then settle
(`rule_on_escalation`, below). The record keeps what a settled value rests on as
the `Basis`, because "one member quoted it", "nobody dissented" and "the evidence
overruled a dissenter" are different things to read afterwards. Telling the
first from the second is the one place a member is counted, and it changes what
the record admits, never the ruling.

**A metric the council left open may be settled once more, by escalation.** The
escalation model's reply settles it only where that reply is the same value in
both orders, its quotation is in the advisory, and -- on a contested metric --
the value is one the council's verified quotations already support. Anything
else leaves the metric as the council left it. So on a contest it can only side
with a value that already has verified evidence behind it, and on an unresolved
metric its quotation has to verify like anyone's.

**The chairman hands over a vector, never a score.** Nothing in this package
imports `src/scoring/`, and if it ever needs to, something has gone wrong.
"""

from typing import Mapping, Sequence

from council.answer import MemberAnswer, MemberReply, weakest_confidence
from council.evidence import is_quotation_from
from council.ruling import (
    Basis,
    ContestedMetric,
    Fallback,
    MetricRuling,
    PublishedFallback,
    SettledMetric,
    UnresolvedMetric,
)
from council.run import MemberFailure
from cvss.metrics import METRIC_ORDER
from cvss.vector import CvssVector


def rule_on_metric(
    metric: str,
    replies: Sequence[MemberReply],
    advisory_text: str,
    fallback: Fallback,
) -> MetricRuling:
    """Reconcile every member's reply about one metric into a single ruling."""
    refuse_foreign_replies(metric, replies)
    answers = [reply for reply in replies if isinstance(reply, MemberAnswer)]
    verified = [answer for answer in answers if is_quotation_from(answer.evidence, advisory_text)]
    if not verified:
        # Either nobody offered a value, or nobody's quotation was in the text.
        # Both are the same result: no evidence this council can stand behind.
        return UnresolvedMetric(metric=metric, fallback=fallback)
    supported = {answer.value for answer in verified}
    if len(supported) > 1:
        return ContestedMetric(metric=metric, candidates=tuple(verified))
    return settle(metric, supported.pop(), answers, verified)


def settle(
    metric: str,
    value: str,
    answers: Sequence[MemberAnswer],
    verified: Sequence[MemberAnswer],
) -> SettledMetric:
    """Record a metric the verified evidence agrees on, and what that agreement rests on."""
    return SettledMetric(
        metric=metric,
        value=value,
        # What the ruling rests on is the verified evidence, so the weakest of
        # those is what the agreement is worth.
        confidence=weakest_confidence(verified),
        basis=basis_of(value, answers),
        supporting=tuple(verified),
    )


def basis_of(value: str, answers: Sequence[MemberAnswer]) -> Basis:
    """Say what a settled value rests on: one quotation, no dissent, or a dissent overruled."""
    # `answers` is every member that offered a quotation, verified or not. One of
    # them alone agrees with nobody, whatever the others declined or guessed.
    if len(answers) == 1:
        return Basis.SOLE
    if any(answer.value != value for answer in answers):
        return Basis.EVIDENCE
    return Basis.AGREED


def rule_on_escalation(
    prior: MetricRuling, reply: MemberReply | MemberFailure, advisory_text: str
) -> MetricRuling:
    """Settle a metric the council left open on the escalation model's reply, or leave it be."""
    refuse_escalating(prior, reply)
    if not escalation_settles(prior, reply, advisory_text):
        return prior
    return SettledMetric(
        metric=prior.metric,
        value=reply.value,
        confidence=reply.confidence,
        basis=Basis.ESCALATED,
        supporting=(reply,),
    )


def escalation_settles(
    prior: MetricRuling, reply: MemberReply | MemberFailure, advisory_text: str
) -> bool:
    """Say whether an escalated reply may settle what the council left open."""
    # Order-stable is the reply's type: `order_check.reconciled` gives an answer
    # only where both orders named its value.
    if not isinstance(reply, MemberAnswer):
        return False
    if not is_quotation_from(reply.evidence, advisory_text):
        return False
    if isinstance(prior, ContestedMetric):
        return reply.value in {candidate.value for candidate in prior.candidates}
    return True


def refuse_escalating(prior: MetricRuling, reply: MemberReply | MemberFailure) -> None:
    """Refuse an escalation of a settled metric, of another metric, or asked in one order."""
    if isinstance(prior, SettledMetric):
        raise ValueError(f"{prior.metric} is settled; only an open metric is escalated")
    if reply.metric != prior.metric:
        raise ValueError(f"{reply.metric} answered where {prior.metric} was escalated")
    if not reply.member.reversed_prompt_version:
        raise ValueError(
            f"{prior.metric} was escalated in one order; an escalation is asked in both"
        )


def agreed_vector(rulings: Mapping[str, MetricRuling], version: str) -> CvssVector:
    """Assemble the one vector the chairman hands over, refusing an unfinished council."""
    refuse_unfinished(rulings)
    metrics = {metric: value_of(rulings[metric]) for metric in METRIC_ORDER}
    return CvssVector(version=version, metrics=metrics)


def value_of(ruling: MetricRuling) -> str:
    """Give the value a ruling carries, refusing one that does not have a value yet."""
    if isinstance(ruling, SettledMetric):
        return ruling.value
    if has_value(ruling):
        return ruling.fallback.value
    raise ValueError(f"{ruling.metric} carries no value to hand over")


def has_value(ruling: MetricRuling) -> bool:
    """Say whether a ruling carries a value a vector could be built from."""
    if isinstance(ruling, SettledMetric):
        return True
    return isinstance(ruling, UnresolvedMetric) and isinstance(ruling.fallback, PublishedFallback)


def refuse_unfinished(rulings: Mapping[str, MetricRuling]) -> None:
    """Refuse to build a vector while a metric is missing, contested, or without a fallback."""
    missing = [metric for metric in METRIC_ORDER if metric not in rulings]
    if missing:
        raise ValueError(f"No ruling on {', '.join(missing)}; a vector needs all eight metrics")
    # Every unfinished metric at once, not the first one found, so a refusal
    # names everything that stops a vector rather than the first thing it met.
    unfinished = sorted(metric for metric, ruling in rulings.items() if not has_value(ruling))
    if unfinished:
        raise ValueError(
            f"No value for {', '.join(unfinished)}; a vector needs one for each metric"
        )


def refuse_foreign_replies(metric: str, replies: Sequence[MemberReply]) -> None:
    """Refuse replies about another metric, which would rule on the wrong one."""
    foreign = sorted({reply.metric for reply in replies if reply.metric != metric})
    if not foreign:
        return
    raise ValueError(f"{', '.join(foreign)} answered where {metric} was asked")
