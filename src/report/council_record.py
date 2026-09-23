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
from typing import Sequence


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
class CouncilNotAsked:
    """A finding no council was put to, and why -- which is not no council having run.

    Three facts a reader has to tell apart, and this is the one that used to look
    like the third: a finding the council **was not asked about**, a finding it
    assessed and could not settle, and a run where nobody was named to ask. A
    scoped run that simply recorded nothing for the findings it skipped said no
    council had run on them, which is false and is the same conflation
    `CouncilWithoutVector` exists to prevent one step earlier.

    `because` is the record's, not this file's: why a finding was skipped is
    decided where the skip is, so the renderings read the sentence rather than
    knowing the reasons.
    """

    advisory_id: str
    because: str

    def __post_init__(self) -> None:
        """Refuse a skip that does not say why, which reads on a report as an oversight."""
        if not self.because:
            raise ValueError(
                f"{self.advisory_id} was not put to the council and no reason was recorded"
            )


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


CouncilOutcome = CouncilAssessment | CouncilWithoutVector | CouncilNotAsked


@dataclass(frozen=True)
class PassedOver:
    """One reason the council was not put to some findings, and which findings they were."""

    because: str
    advisory_ids: tuple[str, ...]


def was_assessed(outcome: CouncilOutcome) -> bool:
    """Say whether a council actually read this advisory, rather than passing over it."""
    return not isinstance(outcome, CouncilNotAsked)


def grouped_by_reason(passed: Sequence[CouncilNotAsked]) -> tuple[PassedOver, ...]:
    """Group the findings the council was not put to by the reason it was not put to them."""
    # Grouped once for every rendering rather than in each: three renderings
    # grouping one list three ways is three chances to group it differently.
    reasons = sorted({one.because for one in passed})
    return tuple(PassedOver(one, named_for(one, passed)) for one in reasons)


def named_for(because: str, passed: Sequence[CouncilNotAsked]) -> tuple[str, ...]:
    """Name every finding passed over for one reason, in the order the record holds them."""
    return tuple(one.advisory_id for one in passed if one.because == because)
