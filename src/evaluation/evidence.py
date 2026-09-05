"""Counts how many findings carry each kind of evidence link.

The proposal asks for the *percentage* of findings carrying code, SBOM/AIBOM and
VEX evidence. This module counts, and never divides, because
`docs/SCHEMAS.md` holds `evaluation.json` to one rule: **no field in that file is
a float**, and it goes further -- "no score is printed as a rate anywhere in the
tool", carved out only for `main.py`'s mapping coverage, which is a scan
statistic rather than a result against a grading key. Two tests pin the printed
half (`tests/cli/test_evaluate_output.py`). So this module counts and never
divides: `findings_considered` travels beside every count, and a reader who
wants a percentage does the division holding the denominator, which is the whole
point of the rule.

Three predicates, each named for the artifact the evidence points into.
"""

from artifacts.finding import is_located


def has_code_evidence(finding: dict) -> bool:
    """Say whether the finding points at a line of the audited source."""
    return is_located(finding)


def has_sbom_evidence(finding: dict) -> bool:
    """Say whether the finding names a component from the bill of materials."""
    return bool(finding.get("component_name") or finding.get("purl"))


def has_vex_evidence(finding: dict) -> bool:
    """Say whether the finding becomes a VEX statement.

    `advisory_id` rather than a rule name: `artifacts/vex.py` branches on that
    exact field, so the two cannot drift.

    It counts *findings* that become `affected` statements, not statements:
    `vex.py` groups by (advisory, component), so two surfaces reaching one
    vulnerable component are two findings and one statement. The document also
    holds `under_investigation` statements built from
    `coverage.advisory_unreached_components`, which no finding carries.
    """
    return bool(finding.get("advisory_id"))


def evidence_counts(findings: list[dict]) -> dict:
    """Count the findings carrying each kind of link, denominator included."""
    return {
        "findings_considered": len(findings),
        "with_code_evidence": sum(1 for f in findings if has_code_evidence(f)),
        "with_sbom_evidence": sum(1 for f in findings if has_sbom_evidence(f)),
        "with_vex_evidence": sum(1 for f in findings if has_vex_evidence(f)),
    }


def pooled_evidence(scored: list[dict]) -> dict:
    """Add up each app's counts, naming the apps they rest on.

    Unconditional, unlike the recall and precision pools: those gate on what a
    grading key claims, while this measures only what the tool produced. But it
    still names its apps, because every pooled block in `evaluation.json` does
    -- a pooled count whose sample is implicit cannot be checked.
    """
    keys = ("findings_considered", "with_code_evidence",
            "with_sbom_evidence", "with_vex_evidence")
    pooled = {key: sum(app["evidence"][key] for app in scored) for key in keys}
    return {"apps_included": sorted(app["app"] for app in scored), **pooled}
