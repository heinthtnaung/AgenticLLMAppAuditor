"""Reading a saved report's explanations back into the records a run carried.

The inverse of `report.json_explanation`. A run with a council records one entry
per finding -- the sources explained, or why they were not -- so the map is
rebuilt entry by entry from the findings. A run with no council recorded no
explanation at all, and its map is empty: every finding's block then only says no
model was asked, which an empty map reproduces.
"""

from typing import Any, Iterable, Mapping

from report.explanation_record import (
    DroppedMetric,
    ExplainedMetric,
    ExplanationRecord,
    SourcesExplained,
    SourcesNotExplained,
)
from report.json_explanation import NOT_RECORDED
from report.load_json import as_list, require, required_object


def explanations_from(
    findings: Iterable[Mapping[str, Any]], council_named: bool
) -> dict[str, ExplanationRecord]:
    """Rebuild the map: an entry per finding a run kept one for, none where no council ran."""
    if not council_named:
        return {}
    entries = (explanation_entry(one) for one in findings)
    return {advisory_id: record for advisory_id, record in entries if record is not None}


def explanation_entry(finding: Mapping[str, Any]) -> tuple[str, ExplanationRecord | None]:
    """Read one finding's explanation back, or None where the run kept none for it."""
    advisory = required_object(finding, "advisory", "finding")
    advisory_id = str(require(advisory, "advisory_id", "finding.advisory"))
    block = required_object(finding, "llm_explanation", f"finding[{advisory_id}]")
    if unrecorded(block):
        return advisory_id, None
    return advisory_id, explanation_from(advisory_id, block)


def unrecorded(block: Mapping[str, Any]) -> bool:
    """Say whether a block is the record's "no explanation kept", which is no map entry at all."""
    return (
        not block.get("assessed")
        and block.get("because") == NOT_RECORDED
        and "model" not in block
        and not block.get("dropped_items")
    )


def explanation_from(advisory_id: str, block: Mapping[str, Any]) -> ExplanationRecord:
    """Read one explanation record: the sources explained, or why they were not."""
    where = f"llm_explanation[{advisory_id}]"
    dropped_list = as_list(block.get("dropped_items") or [], where)
    dropped = tuple(dropped_from(one, where) for one in dropped_list)
    if require(block, "assessed", where):
        item_list = as_list(require(block, "items", where), where)
        items = tuple(item_from(one, where) for one in item_list)
        return SourcesExplained(
            advisory_id, str(require(block, "model", where)),
            str(require(block, "prompt_version", where)), items, dropped,
        )
    return SourcesNotExplained(
        advisory_id, str(require(block, "because", where)), dropped,
        model=str(block.get("model") or ""), prompt_version=str(block.get("prompt_version") or ""),
    )


def item_from(block: Mapping[str, Any], where: str) -> ExplainedMetric:
    """Read one disputed metric the model spoke to."""
    return ExplainedMetric(
        metric=str(require(block, "metric", where)),
        why=str(require(block, "why", where)),
        evidence=str(require(block, "evidence", where)),
        evidence_verified=bool(require(block, "evidence_verified", where)),
    )


def dropped_from(block: Mapping[str, Any], where: str) -> DroppedMetric:
    """Read one item the model offered and nothing kept, with why it was not kept."""
    return DroppedMetric(
        metric=str(require(block, "metric", where)),
        why=str(require(block, "why", where)),
        evidence=str(require(block, "evidence", where)),
        evidence_verified=bool(require(block, "evidence_verified", where)),
        reason=str(require(block, "reason", where)),
    )
