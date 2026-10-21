"""Reading a whole saved report JSON back into the `Report` record it was rendered from.

So a finished audit can be approved without running again: `cli.approve` reads the
record back, re-renders it, checks the re-render matches the saved files byte for
byte, and only then records the human decision. **Scores are recomputed, not
trusted**: every score, band and council figure is recomputed by the same engine a
run uses, so a number the file states but the engine does not reach is refused. The
agreement check is across the three renderings, though, so a value this reads back
and writes out but no rendering shows -- a field the JSON carries and the text and
HTML pages do not -- is neither recomputed nor caught; `cli.approve` says so.

The derived views a record does not store -- the per-finding spreads and bands,
the run's counts -- are not read: the renderers compute them again. What cannot be
recomputed is read straight back: the components and advisories, the council and
explanation projections, the absences, the approval, and the coverage that the
absences and the provenance between them record.
"""

from typing import Any, Mapping

from deps.syft_report import UnidentifiedArtifact
from deps.trivy_secrets import SecretFinding
from findings.finding import Finding
from organisation.approval import Approval, ApprovalOutcome, NotApproved, read_decision
from organisation.risk import FindingRisk
from report.absences import NO_EXPLAINER_ASKED, NOTHING_TO_WEIGH, UNREAD_MANIFEST, Absence, Coverage
from report.council_record import CouncilOutcome
from report.load_council import council_from
from report.load_explanation import explanations_from
from report.load_finding import finding_from
from report.load_json import as_object, require, required_list, required_object
from report.load_provenance import component_count_from, provenance_from
from report.load_risk import risk_from
from report.record import Report


def report_from_json(document: Any, source: str) -> Report:
    """Read a saved report JSON back into the record both renderings read."""
    document = as_object(document, source)
    provenance = provenance_from(document)
    blocks = finding_blocks(document)
    findings = tuple(finding_from(block, f"findings[{i}]") for i, block in enumerate(blocks))
    council_named = council_was_named(blocks)
    not_assessed = absences_from(document)
    risk = risk_map(findings, blocks)
    return Report(
        provenance=provenance,
        findings=findings,
        component_count=component_count_from(document),
        components_without_findings=string_list(document, "components_without_findings"),
        advisories_without_components=string_list(document, "advisories_without_components"),
        overrides_without_findings=string_list(document, "overrides_without_findings"),
        unidentified_artifacts=artifacts_from(document),
        not_assessed=not_assessed,
        council=council_map(findings, blocks),
        explanations=explanations_from(blocks, council_named),
        risk=risk,
        approval=approval_from(required_object(document, "approval", "report")),
        coverage=coverage_from(council_named, bool(risk), not_assessed),
        secrets=secrets_from(document),
    )


def finding_blocks(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Give each finding as the object it must be, numbered so a fault names which one."""
    listed = required_list(document, "findings", "report")
    return [as_object(one, f"findings[{i}]") for i, one in enumerate(listed)]


def council_was_named(blocks: list[Mapping[str, Any]]) -> bool:
    """Say whether the run named a council, by the one thing that renders from it.

    `report.json_explanation` says "no explainer was asked" on every finding of a
    run that named none, and something else on every finding of one that did. That
    choice is the only place a record shows `coverage.council_named`, so it is read
    back from there rather than guessed from whether a council settled anything.
    """
    return any(not no_explainer_asked(block.get("llm_explanation") or {}) for block in blocks)


def no_explainer_asked(block: Mapping[str, Any]) -> bool:
    """Say whether a block is the "no council was asked" note a run with no council writes."""
    return (
        not block.get("assessed")
        and block.get("because") == NO_EXPLAINER_ASKED
        and "model" not in block
        and not block.get("dropped_items")
    )


def council_map(
    findings: tuple[Finding, ...], blocks: list[Mapping[str, Any]]
) -> dict[str, CouncilOutcome]:
    """Rebuild the council map, dropping the findings of a run that named no council."""
    built = (council_entry(one, block) for one, block in zip(findings, blocks))
    return {advisory_id: outcome for advisory_id, outcome in built if outcome is not None}


def council_entry(
    finding: Finding, block: Mapping[str, Any]
) -> tuple[str, CouncilOutcome | None]:
    """Read one finding's council record, keyed by the advisory it is about."""
    advisory_id = finding.advisory.advisory_id
    return advisory_id, council_from(advisory_id, block.get("council"))


def risk_map(
    findings: tuple[Finding, ...], blocks: list[Mapping[str, Any]]
) -> dict[str, FindingRisk]:
    """Rebuild the risk map, dropping the findings this environment scored none."""
    built = (risk_entry(i, one, block) for i, (one, block) in enumerate(zip(findings, blocks)))
    return {advisory_id: risk for advisory_id, risk in built if risk is not None}


def risk_entry(
    index: int, finding: Finding, block: Mapping[str, Any]
) -> tuple[str, FindingRisk | None]:
    """Read one finding's risk, keyed by the advisory it is about."""
    return finding.advisory.advisory_id, risk_from(finding, block, f"findings[{index}]")


def absences_from(document: Mapping[str, Any]) -> tuple[Absence, ...]:
    """Read back what the record says it did not assess, in the order it kept them."""
    listed = required_list(document, "not_assessed", "report")
    return tuple(absence_from(as_object(one, "not_assessed")) for one in listed)


def absence_from(block: Mapping[str, Any]) -> Absence:
    """Read one thing the report does not carry, and why it does not."""
    what = str(require(block, "what", "not_assessed"))
    return Absence(what, str(require(block, "because", "not_assessed")))


def artifacts_from(document: Mapping[str, Any]) -> tuple[UnidentifiedArtifact, ...]:
    """Read back everything catalogued that no advisory could ever be joined to."""
    listed = required_list(document, "unidentified_artifacts", "report")
    return tuple(artifact_from(as_object(one, "unidentified_artifacts")) for one in listed)


def artifact_from(block: Mapping[str, Any]) -> UnidentifiedArtifact:
    """Read one artifact and the ecosystem it was catalogued under."""
    where = "unidentified_artifacts"
    return UnidentifiedArtifact(
        name=str(require(block, "name", where)),
        ecosystem=str(require(block, "ecosystem", where)),
        locations=tuple(str(one) for one in require(block, "locations", where)),
    )


def secrets_from(document: Mapping[str, Any]) -> tuple[SecretFinding, ...]:
    """Read back every secret a rule matched, in the order the record kept them."""
    listed = required_list(document, "secrets", "report")
    return tuple(secret_from(as_object(one, "secrets")) for one in listed)


def secret_from(block: Mapping[str, Any]) -> SecretFinding:
    """Read one secret: the file, its lines, and the rule that matched it."""
    where = "secrets"
    return SecretFinding(
        target=str(require(block, "file", where)),
        start_line=int(require(block, "start_line", where)),
        end_line=int(require(block, "end_line", where)),
        rule_id=str(require(block, "rule_id", where)),
        category=str(require(block, "category", where)),
        severity=str(require(block, "severity", where)),
        title=str(require(block, "title", where)),
    )


def approval_from(block: Mapping[str, Any]) -> ApprovalOutcome:
    """Read the human decision on this audit, or that there is none."""
    if not require(block, "approved", "approval"):
        return NotApproved(str(require(block, "reason", "approval")))
    return Approval(
        approver=str(require(block, "approver", "approval")),
        decision=read_decision(require(block, "decision", "approval")),
        recorded_at=str(require(block, "recorded_at", "approval")),
        note=str(block.get("note") or ""),
        attached_after_run=bool(block.get("attached_after_run")),
    )


def coverage_from(council_named: bool, scored: bool, not_assessed: tuple[Absence, ...]) -> Coverage:
    """Rebuild the coverage no field stores, from the record's absences and whether it scored."""
    unread = tuple(one.what for one in not_assessed if one.because == UNREAD_MANIFEST)
    answers_given = scored or any(one.because == NOTHING_TO_WEIGH for one in not_assessed)
    return Coverage(
        answers_given=answers_given, council_named=council_named, unread_manifests=unread
    )


def string_list(document: Mapping[str, Any], key: str) -> tuple[str, ...]:
    """Read one list of strings the record keeps, in its own order."""
    return tuple(str(one) for one in required_list(document, key, "report"))
