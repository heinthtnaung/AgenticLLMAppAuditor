"""Turning what a council run actually did into what the report can hold.

`docs/COUNCIL.md` keeps each member's answer and evidence, the model, provider,
family and prompt version behind it, whether it ran local or hosted, the
chairman's reasoning and the final vector. The run has all of it, and this is
the step that carries it into the record -- for a member whose call failed as
for one that answered.

It sits in `src/cli/` because it is the only place that may see both sides:
`src/report/` does not import the council, and that boundary is worth a
conversion.
"""

from council.answer import MemberAnswer, MemberFoundNoEvidence, MemberGuessed
from council.evidence import is_quotation_from
from council.ruling import Basis, ContestedMetric, SettledMetric, UnresolvedMetric
from council.run import MemberFailure
from report.council_record import (
    MemberIdentity,
    MemberSaid,
    MetricRuling,
    Outcome,
    SaidKind,
)


def rulings_of(run, advisory_shown: str) -> tuple[MetricRuling, ...]:
    """Record every metric the council ruled on, and what each member said first."""
    return tuple(ruling_of(round_, advisory_shown) for round_ in run.rounds)


def ruling_of(round_, advisory_shown: str) -> MetricRuling:
    """Record one metric: the chairman's decision, and every member behind it."""
    said = tuple(
        said_by(reply, advisory_shown) for reply in (*round_.replies, *round_.failures)
    )
    return MetricRuling(
        metric=round_.metric,
        outcome=outcome_of(round_.ruling),
        said=said,
        value=value_of(round_.ruling),
        basis=basis_of(round_.ruling),
        confidence=confidence_of(round_.ruling),
        fallback_source=fallback_source_of(round_.ruling),
    )


def said_by(reply, advisory_shown: str) -> MemberSaid:
    """Record what one member said, naming which of the four things it did."""
    who = identity_of(reply.member)
    if isinstance(reply, MemberFailure):
        return MemberSaid(member=who, kind=SaidKind.FAILED, reason=reply.reason)
    if isinstance(reply, MemberFoundNoEvidence):
        return MemberSaid(member=who, kind=SaidKind.DECLINED)
    if isinstance(reply, MemberGuessed):
        return MemberSaid(member=who, kind=SaidKind.GUESSED, value=reply.value)
    return answered_by(reply, who, advisory_shown)


def answered_by(reply: MemberAnswer, who: MemberIdentity, advisory_shown: str) -> MemberSaid:
    """Record an answer with its quotation, and whether that quotation checked out."""
    # Whether it verified is the thing that decided the metric, so it travels
    # with the quotation rather than being re-derivable only by the reader.
    return MemberSaid(
        member=who,
        kind=SaidKind.ANSWERED,
        value=reply.value,
        evidence=reply.evidence,
        confidence=reply.confidence.value,
        verified=is_quotation_from(reply.evidence, advisory_shown),
    )


def identity_of(member) -> MemberIdentity:
    """Copy a member's identity into the report's own terms."""
    return MemberIdentity(
        name=member.name,
        provider=member.provider,
        model=member.model,
        family=member.family,
        ran_local=member.ran_local,
        prompt_version=member.prompt_version,
    )


def outcome_of(ruling) -> Outcome:
    """Name what the chairman made of one metric."""
    if isinstance(ruling, SettledMetric):
        return Outcome.SETTLED
    if isinstance(ruling, ContestedMetric):
        return Outcome.CONTESTED
    return Outcome.UNRESOLVED


def value_of(ruling) -> str:
    """Give the value a ruling carries, which a contested one does not have."""
    if isinstance(ruling, SettledMetric):
        return ruling.value
    if isinstance(ruling, UnresolvedMetric):
        return getattr(ruling.fallback, "value", "")
    return ""


def nothing_cross_checked(run) -> bool:
    """Say whether nothing in a run was cross-checked: one member reached, or every basis sole."""
    # Two members reached is not two members checked: one that guessed every
    # metric leaves each resting on the other's quotation alone.
    return run.single_assessor or all(
        getattr(round_.ruling, "basis", None) is Basis.SOLE for round_ in run.rounds
    )


def basis_of(ruling) -> str:
    """Say what settled a metric, in the chairman's own words."""
    basis = getattr(ruling, "basis", None)
    return basis.value if isinstance(basis, Basis) else ""


def confidence_of(ruling) -> str:
    """Give the confidence a settled metric rests on."""
    return ruling.confidence.value if isinstance(ruling, SettledMetric) else ""


def fallback_source_of(ruling) -> str:
    """Name the published source an unresolved metric fell back to, if one did."""
    if not isinstance(ruling, UnresolvedMetric):
        return ""
    return getattr(ruling.fallback, "source", "")
