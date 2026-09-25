"""What the council did, in the audit record, in full.

`docs/COUNCIL.md` keeps each member's answer and evidence, the model, provider,
family and prompt version behind it, whether it ran local or hosted, the
chairman's reasoning and the final vector. All of it is here: the terminal page
chooses what a reader needs first, the record chooses nothing.

The family is on every member because **a roster's agreement means nothing
without knowing whether its members share a lineage** -- five models of one
family agreeing is one opinion in five hats, and a reader cannot tell unless the
record says so.
"""

from typing import Any

from report.council_beside import figure_of
from report.council_record import CouncilAssessment, CouncilNotAsked, MemberSaid, MetricRuling


def council_of(report, advisory_id: str) -> dict[str, Any] | None:
    """Give what the council did for an advisory, or null where no council ran at all."""
    outcome = report.council.get(advisory_id)
    if outcome is None:
        return None
    if isinstance(outcome, CouncilNotAsked):
        # Not the same as null. A council ran on this audit and was not put to
        # this finding, and why it was not is a result rather than an omission.
        return {"ran": False, "because": outcome.because}
    settled = isinstance(outcome, CouncilAssessment)
    return {
        "ran": True,
        "vector": outcome.vector if settled else None,
        "base_score": figure_of(outcome).base_score if settled else None,
        "single_assessor": outcome.single_assessor,
        # Of a vector only: two members reached is not two members checked.
        "nothing_cross_checked": outcome.nothing_cross_checked if settled else None,
        "unresolved_metrics": list(getattr(outcome, "unresolved_metrics", ())),
        "contested_metrics": list(getattr(outcome, "contested_metrics", ())),
        "metrics": [ruling_of(one) for one in outcome.rulings],
    }


def ruling_of(ruling: MetricRuling) -> dict[str, Any]:
    """Give one metric: what the chairman decided, and every member behind it."""
    return {
        "metric": ruling.metric,
        "outcome": ruling.outcome.value,
        "value": ruling.value or None,
        "basis": ruling.basis or None,
        "confidence": ruling.confidence or None,
        "fallback_source": ruling.fallback_source or None,
        "members": [said_of(one) for one in ruling.said],
    }


def said_of(said: MemberSaid) -> dict[str, Any]:
    """Give what one member said, and enough of it to reconstruct the roster."""
    return {
        "member": said.member.name,
        "provider": said.member.provider,
        "model": said.member.model,
        "family": said.member.family,
        "ran_local": said.member.ran_local,
        "prompt_version": said.member.prompt_version,
        "said": said.kind.value,
        "value": said.value or None,
        "evidence": said.evidence or None,
        "confidence": said.confidence or None,
        "evidence_verified": said.verified,
        "reason": said.reason or None,
    }
