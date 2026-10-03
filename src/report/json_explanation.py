"""Why the published sources differ, in the audit record: the model's words beside what was checked.

Every finding carries `llm_explanation`. Assessed, it names the model and the
prompt version and lists each disputed metric the model spoke to: its `why`,
the model's own prose that nothing checked, and its `evidence`, a quotation
found in the advisory. `evidence_verified` is true on every item, because no
other is kept, and `why_checked` is false on every item, so a machine reader
cannot take the first for the second. `dropped` counts the items not kept, and
`dropped_items` holds each with its `reason`, its quotation checked all the same.
Not assessed, it says why: nobody asked, the sources agree, or no explanation
quoted the advisory, and its `dropped_items` hold what the model offered. Where a
model was asked it names the model and the prompt version as an assessed one
does, so dropped model output always says what produced it; where none was, it
names neither.
"""

from typing import Any

from report.absences import NO_EXPLAINER_ASKED
from report.explanation_record import (
    DroppedMetric,
    ExplainedMetric,
    ExplanationRecord,
    SourcesNotExplained,
)

# Said only of a record a council was named for that holds nothing for this finding.
NOT_RECORDED = "no explanation was recorded for this finding"


def explanation_of(report, advisory_id: str) -> dict[str, Any]:
    """Give why one finding's sources differ as a model wrote it, or say why there is none."""
    record = report.explanations.get(advisory_id)
    if record is None:
        because = NOT_RECORDED if report.coverage.council_named else NO_EXPLAINER_ASKED
        return {"assessed": False, "because": because, "dropped_items": []}
    dropped = [dropped_of(one) for one in record.dropped_items]
    if isinstance(record, SourcesNotExplained):
        return not_explained_of(record, dropped)
    return {
        "assessed": True,
        **named_by(record),
        "items": [item_of(one) for one in record.items],
        "dropped": record.dropped,
        "dropped_items": dropped,
    }


def not_explained_of(record: SourcesNotExplained, dropped: list[dict[str, Any]]) -> dict[str, Any]:
    """Say why a finding was not explained, naming the model and prompt where one was asked."""
    named = named_by(record) if record.asked else {}
    return {"assessed": False, **named, "because": record.because, "dropped_items": dropped}


def named_by(record: ExplanationRecord) -> dict[str, str]:
    """Name the model that was asked and the version of the prompt it was asked with."""
    return {"model": record.model, "prompt_version": record.prompt_version}


def dropped_of(item: DroppedMetric) -> dict[str, Any]:
    """Give one item the model offered and nothing kept, with why it was not kept."""
    return {
        "metric": item.metric,
        "why": item.why,
        "evidence": item.evidence,
        "evidence_verified": item.evidence_verified,
        "why_checked": False,
        "reason": item.reason,
    }


def item_of(item: ExplainedMetric) -> dict[str, Any]:
    """Give one disputed metric the model spoke to."""
    return {
        "metric": item.metric,
        "why": item.why,
        "evidence": item.evidence,
        "evidence_verified": item.evidence_verified,
        # Only the quotation is held to the advisory; the prose beside it never is.
        "why_checked": False,
    }
