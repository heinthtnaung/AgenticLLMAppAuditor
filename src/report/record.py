"""The report record: everything the run computed, and everything it did not.

Built once and rendered twice, so the audit artefact and the thing a person
reads are two views of one record rather than one derived from the other's
formatting.

**A score nobody can re-derive is not a score.** `docs/SCORING_MODEL.md` makes
that the rule the record is shaped by: every source's vector travels beside its
number, so a reader with the published equations reproduces every figure here
without this tool. The published scores stand side by side and no source is
chosen as the winner; a council's reading is carried beside them and never
weighed in.

**The absences are part of the record.** What was not assessed is a field, not
an omission; `report.absences` names each one and says why.
"""

from dataclasses import dataclass, field
from typing import Iterable, Mapping

from deps.syft_report import Catalogue, UnidentifiedArtifact
from deps.trivy_report import Advisory
from findings.finding import Finding, unmatched_purls
from organisation.approval import ApprovalOutcome, NotApproved
from organisation.risk import FindingRisk
from report.absences import NO_APPROVAL_GIVEN, Absence, Coverage, absences
from report.council_record import CouncilOutcome
from report.provenance import RunProvenance


@dataclass(frozen=True)
class Report:
    """One audit: what was found, what matched nothing, and what was not assessed."""

    provenance: RunProvenance
    findings: tuple[Finding, ...]
    component_count: int
    # Two different results, and easily confused for each other.
    # A component nothing was published against looks clean and may be; an
    # advisory matching no component is a CVE that fell out of the join, which
    # is a report that looks clean and is not.
    components_without_findings: tuple[str, ...]
    advisories_without_components: tuple[str, ...]
    # A fourth: an answer file naming an advisory this scan did not find. Not
    # refused, because a file reused across repositories will legitimately name
    # advisories absent from one of them -- but a deliberate override that did
    # not apply moved a finding a band with nothing said, so it is counted.
    overrides_without_findings: tuple[str, ...]
    # A third kind of nothing: catalogued, joinable to nothing by nature, and so
    # never a finding. Counted rather than dropped, because a catalogue entry
    # dropped silently is how a report loses a CVE.
    unidentified_artifacts: tuple[UnidentifiedArtifact, ...]
    not_assessed: tuple[Absence, ...]
    council: Mapping[str, CouncilOutcome] = field(default_factory=dict)
    risk: Mapping[str, FindingRisk] = field(default_factory=dict)
    approval: ApprovalOutcome = field(default_factory=lambda: NotApproved(NO_APPROVAL_GIVEN))
    coverage: Coverage = Coverage()


def build_report(
    provenance: RunProvenance,
    catalogue: Catalogue,
    findings: Iterable[Finding],
    advisories_by_purl: Mapping[str, tuple[Advisory, ...]],
    council: Iterable[CouncilOutcome] = (),
    risk: Iterable[FindingRisk] = (),
    approval: ApprovalOutcome | None = None,
    overridden: Iterable[str] = (),
    coverage: Coverage = Coverage(),
) -> Report:
    """Gather one run into the record both renderings read."""
    raised = tuple(findings)
    settled, weighed = by_advisory(council), by_advisory(risk)
    decided = approval or NotApproved(NO_APPROVAL_GIVEN)
    return Report(
        provenance=provenance,
        findings=raised,
        component_count=len(catalogue.components),
        components_without_findings=purls_without_findings(catalogue, raised),
        advisories_without_components=unmatched_purls(catalogue.components, advisories_by_purl),
        unidentified_artifacts=catalogue.unidentified,
        overrides_without_findings=overrides_without_findings(overridden, raised),
        not_assessed=absences(settled, weighed, decided, coverage),
        council=settled,
        risk=weighed,
        approval=decided,
        coverage=coverage,
    )


def by_advisory(entries: Iterable) -> dict:
    """Index anything carrying an advisory id by the advisory it is about."""
    return {one.advisory_id: one for one in entries}


def purls_without_findings(catalogue: Catalogue, findings: tuple[Finding, ...]) -> tuple[str, ...]:
    """Name the installed components nothing was published against."""
    affected = {finding.component.purl for finding in findings}
    return tuple(sorted(one.purl for one in catalogue.components if one.purl not in affected))


def overrides_without_findings(
    overridden: Iterable[str], findings: tuple[Finding, ...]
) -> tuple[str, ...]:
    """Name the answer overrides that matched nothing this scan found."""
    found = {finding.advisory.advisory_id for finding in findings}
    return tuple(sorted(one for one in overridden if one not in found))
