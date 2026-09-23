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

NO_QUESTION_LIBRARY = (
    "the approved question library is not built, so no organisation answered anything"
)
NO_APPROVAL_CAPTURE = "nothing in this tool captures a human's approval yet"
# Said only when no council ran at all. A council that ran and settled nothing
# is a different fact and has its own record; conflating the two put a false
# statement in an audit record, reachable from the command line.
NO_COUNCIL_RUN = "no council assessed this run, so no source has been chosen between"


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
class AdvisoryDatabase:
    """The advisory database this scan joined against, by its own build date."""

    built_at: str

    def __post_init__(self) -> None:
        """Refuse a database that names no build date, which is the same as none at all."""
        if not self.built_at.strip():
            raise ValueError("An advisory database must give the date it was built")


@dataclass(frozen=True)
class UnknownAdvisoryDatabase:
    """No build date could be read, so nothing says this scan saw a database at all."""

    reason: str

    def __post_init__(self) -> None:
        """Refuse an unexplained absence of the one check against a silent clean report."""
        if not self.reason:
            raise ValueError("A missing database date must say why it is missing")


Database = AdvisoryDatabase | UnknownAdvisoryDatabase


@dataclass(frozen=True)
class RunProvenance:
    """What produced this report, so a reader can judge whether to believe it."""

    repository: str
    syft_version: str
    trivy_version: str
    database: Database

    def __post_init__(self) -> None:
        """Refuse provenance a reader could not reproduce the run from."""
        missing = [
            name
            for name in ("repository", "syft_version", "trivy_version")
            if not getattr(self, name)
        ]
        if missing:
            raise ValueError(f"A run's provenance needs {', '.join(missing)}")
        if not isinstance(self.database, (AdvisoryDatabase, UnknownAdvisoryDatabase)):
            raise TypeError(f"A run needs a database, not {type(self.database).__name__}")


@dataclass(frozen=True)
class CouncilAssessment:
    """A council that settled every metric for one advisory, and the vector it handed over."""

    advisory_id: str
    vector: str
    single_assessor: bool


@dataclass(frozen=True)
class CouncilWithoutVector:
    """A council that ran on one advisory and could not settle a vector, and what stopped it.

    Its own type rather than an assessment with the vector left out. A council
    that ran and settled nothing is not a council that did not run: the second
    is an absence, the first is a result, and what it could not settle is the
    escalation policy's whole input.
    """

    advisory_id: str
    single_assessor: bool
    unresolved_metrics: tuple[str, ...] = ()
    contested_metrics: tuple[str, ...] = ()


CouncilOutcome = CouncilAssessment | CouncilWithoutVector


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
    # A third kind of nothing: catalogued, joinable to nothing by nature, and so
    # never a finding. Counted rather than dropped, because the reason the
    # scanner used to refuse these was that dropping one silently loses a CVE.
    unidentified_artifacts: tuple[UnidentifiedArtifact, ...]
    not_assessed: tuple[Absence, ...]
    council: Mapping[str, CouncilOutcome] = field(default_factory=dict)


def build_report(
    provenance: RunProvenance,
    catalogue: Catalogue,
    findings: Iterable[Finding],
    advisories_by_purl: Mapping[str, tuple[Advisory, ...]],
    council: Iterable[CouncilOutcome] = (),
) -> Report:
    """Gather one run into the record both renderings read."""
    catalogued = catalogue.components
    raised = tuple(findings)
    settled = {assessment.advisory_id: assessment for assessment in council}
    affected = {finding.component.purl for finding in raised}
    return Report(
        provenance=provenance,
        findings=raised,
        component_count=len(catalogued),
        components_without_findings=tuple(
            sorted(one.purl for one in catalogued if one.purl not in affected)
        ),
        advisories_without_components=unmatched_purls(catalogued, advisories_by_purl),
        unidentified_artifacts=catalogue.unidentified,
        not_assessed=absences(settled),
        council=settled,
    )


def absences(council: Mapping[str, CouncilOutcome]) -> tuple[Absence, ...]:
    """Name what this build cannot assess, so no reader takes silence for a nil result."""
    named = [
        Absence("Organisation Risk Score", NO_QUESTION_LIBRARY),
        Absence("Approval record", NO_APPROVAL_CAPTURE),
    ]
    if not council:
        named.append(Absence("Council ruling", NO_COUNCIL_RUN))
    return tuple(named)
