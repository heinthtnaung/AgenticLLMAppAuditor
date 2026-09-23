"""What a council did, in terms the report can hold without importing the council.

`docs/COUNCIL.md` keeps, per assessment, **each member's answer and evidence**,
the model, provider, family and prompt version behind it, whether that member
ran local or hosted, the chairman's reasoning and the final vector. The run
computes all of it and the record used to carry three fields of it.

These are a projection, not the council's own types. `src/report/` depends on
neither the council nor the scoring engine, and bridging the packages to save a
few dataclasses would trade a boundary for a shortcut.

**One record per member with the kind named, rather than four types.** Everywhere
else in this project an absence has its own type, because confusing it with a
value changes a number. Here the arithmetic has already happened -- `council.ruling`
and `council.answer` hold those four distinctions where they decide something --
and what is left is a row to write down. The kind is on every row, so nothing is
told apart by remembering to check.
"""

from dataclasses import dataclass
from enum import Enum


class SaidKind(Enum):
    """What a member did about one metric."""

    ANSWERED = "answered"
    DECLINED = "declined"
    GUESSED = "guessed"
    FAILED = "failed"


class Outcome(Enum):
    """What the chairman made of one metric."""

    SETTLED = "settled"
    CONTESTED = "contested"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class MemberIdentity:
    """Which member spoke, and enough of it to reconstruct the roster afterwards."""

    name: str
    provider: str
    model: str
    family: str
    ran_local: bool
    prompt_version: str


@dataclass(frozen=True)
class MemberSaid:
    """What one member said about one metric, and who it was.

    `value`, `evidence` and `confidence` are empty for the kinds that have none:
    a member that declined named no value, one that guessed quoted nothing, and
    one that failed said nothing at all. `kind` says which, on every row.
    """

    member: MemberIdentity
    kind: SaidKind
    value: str = ""
    evidence: str = ""
    confidence: str = ""
    verified: bool = False
    reason: str = ""


@dataclass(frozen=True)
class MetricRuling:
    """What the chairman decided about one metric, and what every member said first."""

    metric: str
    outcome: Outcome
    said: tuple[MemberSaid, ...]
    value: str = ""
    basis: str = ""
    confidence: str = ""
    fallback_source: str = ""


@dataclass(frozen=True)
class CouncilAssessment:
    """A council that settled every metric for one advisory, and the vector it handed over."""

    advisory_id: str
    vector: str
    single_assessor: bool
    rulings: tuple[MetricRuling, ...] = ()


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
    rulings: tuple[MetricRuling, ...] = ()


CouncilOutcome = CouncilAssessment | CouncilWithoutVector
