"""The organisation's half of the audit record: its risk scores and its approval.

**A score nobody can re-derive is not a score**, so every answer that produced
one is here with the weight it carried and what it contributed -- a reader with
`docs/SCORING_MODEL.md` reaches the same number without this tool. The raw total
is written beside the clamped score because the clamp is invisible in the score
alone, and the clamp is the step the design is most particular about.

The categories are written once per finding rather than once per source: the
environment does not change with who published a vector, only the technical term
does, and that is exactly why a finding is scored per source at all.
"""

from typing import Any

from organisation.approval import Approval
from report.record import Report


def risk_of(report: Report, advisory_id: str) -> dict[str, Any] | None:
    """Give what this environment makes of a finding, or null where nobody answered."""
    weighed = report.risk.get(advisory_id)
    if weighed is None:
        return None
    # The categories are the same for every source, so they are written once:
    # only the technical term moves, which is the whole point of scoring per source.
    return {
        "scores": [scored_of(one) for one in weighed.scores],
        "bands": list(weighed.bands),
        "band_depends_on_the_source": weighed.band_depends_on_the_source,
        "provisional": weighed.is_provisional,
        "categories": categories_of(weighed.scores[0]),
    }


def scored_of(scored: Any) -> dict[str, Any]:
    """Give one organisation score and the technical severity it was weighed from."""
    return {
        "technical_from": technical_from(scored.technical),
        "technical_score": scored.technical_score,
        "score": scored.score,
        "band": scored.band,
        "provisional": scored.is_provisional,
        "unknown_questions": list(scored.unknown_questions),
    }


def technical_from(technical: Any) -> str:
    """Say where a technical severity came from, including when nobody offered one."""
    return getattr(technical, "derived_from", None) or technical.reason


def categories_of(scored: Any) -> dict[str, Any]:
    """Give every category with the answers and weights that produced it."""
    named = (
        ("exposure", scored.exposure),
        ("business", scored.business),
        ("threat", scored.threat),
    )
    return {name: category_of(category) for name, category in named}


def category_of(category: Any) -> dict[str, Any]:
    """Give one category's score, its raw total, and every answer behind it."""
    # Both totals: the clamp is invisible in the score alone, and a reader
    # re-deriving the number by hand needs to see where it was held.
    return {
        "score": category.score,
        "raw_total": category.raw_total,
        "clamped": category.was_clamped,
        "answers": [answered_of(one) for one in category.answers],
    }


def answered_of(answered: Any) -> dict[str, Any]:
    """Give one answer, the question it answers, and what it was worth."""
    return {
        "question_id": answered.question.question_id,
        "question": answered.question.text,
        "answer": answered.answer.value,
        "yes_weight": answered.question.yes_weight,
        "contribution": answered.contribution,
    }


def approval_of(report: Report) -> dict[str, Any]:
    """Give the human decision on this audit, or say plainly that there is none."""
    decided = report.approval
    if not isinstance(decided, Approval):
        return {"approved": False, "reason": decided.reason}
    return {
        "approved": True,
        "approver": decided.approver,
        "decision": decided.decision.value,
        "recorded_at": decided.recorded_at,
        "note": decided.note,
    }
