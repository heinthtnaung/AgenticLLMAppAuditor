"""The report record: everything the run computed, and everything it did not.

Built once and rendered twice, so the audit artefact and the thing a person
reads are two views of one record rather than one derived from the other's
formatting.

**A score nobody can re-derive is not a score.** `docs/SCORING_MODEL.md` makes
that the rule the record is shaped by: every source's vector travels beside its
number, so a reader with the published equations reproduces every figure here
without this tool. No source is preferred and no winner is named -- which source
wins is open until the council settles it.

**The absences are part of the record.** A report of a half-built tool that
looks complete is worse than one that says what it did not do: an Organisation
Risk Score printed as 0 reads as a finding assessed and found harmless. So what
was not assessed is a field, not an omission.
"""

from dataclasses import dataclass, field
from typing import Iterable, Mapping

from deps.syft_report import Catalogue, UnidentifiedArtifact
from deps.trivy_report import Advisory
from findings.finding import Finding, unmatched_purls
from organisation.approval import ApprovalOutcome, NotApproved
from organisation.risk import FindingRisk
from report.council_record import CouncilOutcome, was_assessed
from report.provenance import RunProvenance

NO_ANSWERS_GIVEN = "no organisation answers were supplied, so no environment was weighed"
NO_APPROVAL_GIVEN = "nobody has approved or overridden this audit"
# Said only when no council ran at all. A council that ran and settled nothing
# is a different fact and has its own record; conflating the two put a false
# statement in an audit record, reachable from the command line.
NO_COUNCIL_RUN = "no council assessed this run, so no source has been chosen between"
# And a third: members were named and every finding was passed over, so the
# council assessed none. Naming no absence there leaves a reader with neither a
# ruling nor a reason there is none.
NOTHING_WAS_PUT_TO_IT = "the council was put to no finding, so no source has been chosen between"


@dataclass(frozen=True)
class Absence:
    """Something this report does not carry, named so it is not read as a nil result."""

    what: str
    because: str

    def __post_init__(self) -> None:
        """Refuse an absence that does not say what is missing or why."""
        if not self.what or not self.because:
            raise ValueError("An absence must say what is missing and why")


@dataclass(frozen=True)
class Report:
    """One audit: what was found, what matched nothing, and what was not assessed."""

    provenance: RunProvenance
    findings: tuple[Finding, ...]
    component_count: int
    # Two different results, and the tool has had both confused for each other.
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
    # never a finding. Counted rather than dropped, because the reason the
    # scanner used to refuse these was that dropping one silently loses a CVE.
    unidentified_artifacts: tuple[UnidentifiedArtifact, ...]
    not_assessed: tuple[Absence, ...]
    council: Mapping[str, CouncilOutcome] = field(default_factory=dict)
    risk: Mapping[str, FindingRisk] = field(default_factory=dict)
    approval: ApprovalOutcome = field(default_factory=lambda: NotApproved(NO_APPROVAL_GIVEN))


def build_report(
    provenance: RunProvenance,
    catalogue: Catalogue,
    findings: Iterable[Finding],
    advisories_by_purl: Mapping[str, tuple[Advisory, ...]],
    council: Iterable[CouncilOutcome] = (),
    risk: Iterable[FindingRisk] = (),
    approval: ApprovalOutcome | None = None,
    overridden: Iterable[str] = (),
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
        not_assessed=absences(settled, weighed, decided),
        council=settled,
        risk=weighed,
        approval=decided,
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


def absences(
    council: Mapping[str, CouncilOutcome],
    risk: Mapping[str, FindingRisk],
    approval: ApprovalOutcome,
) -> tuple[Absence, ...]:
    """Name what this run did not assess, so no reader takes silence for a nil result."""
    named = []
    if not risk:
        named.append(Absence("Organisation Risk Score", NO_ANSWERS_GIVEN))
    if isinstance(approval, NotApproved):
        named.append(Absence("Approval record", approval.reason))
    return tuple([*named, *council_absence(council)])


def council_absence(council: Mapping[str, CouncilOutcome]) -> list[Absence]:
    """Name a missing council ruling, keeping "asked about nothing" apart from "never ran"."""
    if any(was_assessed(one) for one in council.values()):
        return []
    return [Absence("Council ruling", NO_COUNCIL_RUN if not council else NOTHING_WAS_PUT_TO_IT)]
