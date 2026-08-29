"""Assembles the whole run's evaluation document from the per-app scores.

Separate from `scorer.py`, which answers "how did the tool do on this app".
This answers "what may be said across the corpus", and the two have different
readers: a per-app row can be quoted, a pooled total cannot be quoted without
the apps it rests on.

Pooled counts, never a mean: an average hides which app carried
the number. F1 is refused rather than omitted, because an absent field reads as
unimplemented and this is a decision.
"""

SCHEMA_VERSION = 1

# Which system produced the findings being scored. Carried inside the record,
# not only in the filename, so a row copied into a write-up keeps its label.
AGENTIC_AUDITOR = "agentic_auditor"
SCORED_SYSTEMS = (AGENTIC_AUDITOR, "baseline_static_rules", "baseline_sbom_only")


def _totals(scored: list[dict]) -> dict:
    """Pool the counts, each block naming the apps it rests on."""
    recall_apps = [a for a in scored if a["recall_reportable"]]
    precision_apps = [a for a in scored if a["precision_reportable"]]
    both = [a for a in scored if a["recall_reportable"] and a["precision_reportable"]]
    return {
        "recall": {
            "apps_included": sorted(a["app"] for a in recall_apps),
            "true_positives": sum(a["true_positives"] for a in recall_apps),
            "false_negatives": sum(a["false_negatives"] for a in recall_apps),
            "key_finding_count": sum(a["key_finding_count"] for a in recall_apps),
        },
        "precision": {
            "apps_included": sorted(a["app"] for a in precision_apps),
            "true_positives": sum(a["true_positives"] for a in precision_apps),
            "false_positives": sum(a["false_positives"] for a in precision_apps),
            "produced_finding_count": sum(a["produced_finding_count"] for a in precision_apps),
        },
        "f1_reportable": bool(both),
        "f1_blocked_reason": None if both else "no app supports both precision and recall",
    }


def build_evaluation(scored: list[dict], system: str = AGENTIC_AUDITOR) -> dict:
    """Return the evaluation document for one system over every app scored."""
    if system not in SCORED_SYSTEMS:
        raise ValueError(f"unknown system {system!r}; expected one of {SCORED_SYSTEMS}")
    ordered = sorted(scored, key=lambda a: a["app"])
    return {
        "schema_version": SCHEMA_VERSION,
        "system": system,
        "app_count": len(ordered),
        "apps": ordered,
        "totals": _totals(ordered),
    }
