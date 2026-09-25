"""What a record says it does not carry, and why: named, so no absence reads as a nil result.

A report of a half-built tool that looks complete is worse than one that says
what it did not do: an Organisation Risk Score printed as 0 reads as a finding
assessed and found harmless. So each thing a run did not assess is an `Absence`
with its reason, and the reasons are kept apart where the causes differ --
nobody asked, there was nothing to ask about, or a manifest could not be read.

`Coverage` is what the operator asked the run for and what it could not read,
which the absences alone are drawn from; `report.record` carries both.
"""

from dataclasses import dataclass
from typing import Mapping

from organisation.approval import ApprovalOutcome, NotApproved
from organisation.risk import FindingRisk
from report.council_record import CouncilOutcome, was_assessed

NO_ANSWERS_GIVEN = "no organisation answers were supplied, so no environment was weighed"
NO_APPROVAL_GIVEN = "nobody has approved or overridden this audit"
# Said only when no council ran at all. A council that ran and settled nothing
# is a different fact and has its own record; conflating the two put a false
# statement in an audit record, reachable from the command line.
NO_COUNCIL_RUN = (
    "no council assessed this run, so no council reading stands beside the published scores"
)
# And a third: members were named and every finding was passed over, so the
# council assessed none. Naming no absence there leaves a reader with neither a
# ruling nor a reason there is none.
NOTHING_WAS_PUT_TO_IT = (
    "the council was put to no finding, so no council reading stands beside the published scores"
)
# A run that found nothing has no score and no ruling even when the operator
# asked for both, and saying nobody asked would be the wrong cause.
NOTHING_TO_WEIGH = "answers were supplied, but there was no finding to weigh them against"
NOTHING_TO_PUT = "council members were named, but there was no finding to put to them"
# Said of each manifest the scan read no version from; `deps.manifests` says what counts as read.
UNREAD_MANIFEST = "no lock file Syft reads is beside it, so no version it declares was checked"
# Said under the heading when nothing is absent, because an empty heading is the
# silence the section exists to prevent. It names what is present rather than
# claiming everything was assessed: a scoped council leaves findings unasked,
# and says so in its own section.
NOTHING_ABSENT = (
    "Nothing: the Organisation Risk Score, the approval record and a council ruling are all here."
)


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
class Coverage:
    """What the operator asked this run for, and the manifests it could read nothing from.

    An empty risk score or council can mean nobody asked or there was nothing to
    ask about, and only this tells the two apart.
    """

    answers_given: bool = False
    council_named: bool = False
    unread_manifests: tuple[str, ...] = ()


def absences(
    council: Mapping[str, CouncilOutcome],
    risk: Mapping[str, FindingRisk],
    approval: ApprovalOutcome,
    coverage: Coverage,
) -> tuple[Absence, ...]:
    """Name what this run did not assess, so no reader takes silence for a nil result."""
    named = [*manifest_absences(coverage), *risk_absence(risk, coverage.answers_given)]
    if isinstance(approval, NotApproved):
        named.append(Absence("Approval record", approval.reason))
    return tuple([*named, *council_absence(council, coverage.council_named)])


def manifest_absences(coverage: Coverage) -> list[Absence]:
    """Name each manifest the scan read no version from, first, because it bounds every count."""
    return [Absence(path, UNREAD_MANIFEST) for path in coverage.unread_manifests]


def risk_absence(risk: Mapping[str, FindingRisk], answers_given: bool) -> list[Absence]:
    """Name a missing risk score, keeping "nothing to weigh" apart from "nobody answered"."""
    if risk:
        return []
    because = NOTHING_TO_WEIGH if answers_given else NO_ANSWERS_GIVEN
    return [Absence("Organisation Risk Score", because)]


def council_absence(council: Mapping[str, CouncilOutcome], council_named: bool) -> list[Absence]:
    """Name a missing council ruling, keeping "asked about nothing" apart from "never ran"."""
    if any(was_assessed(one) for one in council.values()):
        return []
    return [Absence("Council ruling", council_reason(council, council_named))]


def council_reason(council: Mapping[str, CouncilOutcome], council_named: bool) -> str:
    """Say why there is no ruling: every finding passed over, none to put, or no council named."""
    if council:
        return NOTHING_WAS_PUT_TO_IT
    return NOTHING_TO_PUT if council_named else NO_COUNCIL_RUN
