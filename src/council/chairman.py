"""Reconciling n members' answers into one ruling per metric, and then into a vector.

**Nothing here counts members towards a ruling.** `docs/COUNCIL.md` forbids a
majority vote at any n, because members built on one base model share its
mistakes, so four answers are four pieces of evidence and not four votes. What
decides is whether the quotation verifies: an answer whose evidence is not in the
advisory supports nothing, however many members give it.

That makes the design's first two rules one computation. Among the answers whose
quotation verified, either they support one value -- settled -- or they do not,
and the metric is contested and belongs to the escalation policy. The record
keeps what a settled value rests on as the `Basis`, because "one member quoted
it", "nobody dissented" and "the evidence overruled a dissenter" are different
things to read afterwards. Telling the first from the second is the one place a
member is counted, and it changes what the record admits, never the ruling.

**The chairman hands over a vector, never a score.** Nothing in this package
imports `src/scoring/`, and if it ever needs to, something has gone wrong.
"""

from typing import Mapping, Sequence

from cvss.metrics import METRIC_ORDER
from cvss.vector import CvssVector
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
    # Every unfinished metric at once, not the first one found: a council that
    # left two metrics contested should send both to the escalation policy in
    # one round rather than learn about the second after settling the first.
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
