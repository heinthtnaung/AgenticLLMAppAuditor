"""Why the published sources differ, in the audit record: the model's words beside what was checked.

Every finding carries `llm_explanation`. Assessed, it names the model and the
prompt version and lists each disputed metric the model spoke to: its `why`,
the model's own prose that nothing checked, and its `evidence`, a quotation
found in the advisory. `evidence_verified` is true on every item, because no
other is kept, and `why_checked` is false on every item, so a machine reader
cannot take the first for the second. `dropped` counts the items not kept.
Not assessed, it says why: nobody asked, the sources agree, or no explanation
quoted the advisory.
"""

from typing import Any

from report.absences import NO_EXPLAINER_ASKED
from report.explanation_record import ExplainedMetric, SourcesNotExplained

# Said only of a record a council was named for that holds nothing for this finding.
NOT_RECORDED = "no explanation was recorded for this finding"


def explanation_of(report, advisory_id: str) -> dict[str, Any]:
    """Give why one finding's sources differ as a model wrote it, or say why there is none."""
    record = report.explanations.get(advisory_id)
    if record is None:
        because = NOT_RECORDED if report.coverage.council_named else NO_EXPLAINER_ASKED
        return {"assessed": False, "because": because}
    if isinstance(record, SourcesNotExplained):
        return {"assessed": False, "because": record.because}
    return {
        "assessed": True,
        "model": record.model,
        "prompt_version": record.prompt_version,
        "items": [item_of(one) for one in record.items],
        "dropped": record.dropped,
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
