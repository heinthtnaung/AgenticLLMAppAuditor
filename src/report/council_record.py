"""What a council did, in terms the report can hold without importing the council.

`docs/COUNCIL.md` keeps, per assessment, **each member's answer and evidence**,
the model, provider, family and prompt version behind it, whether that member
ran local or hosted, the chairman's reasoning and the final vector. The run
computes all of it, and this record carries all of it.

These are a projection, not the council's own types: `src/report/` does not
import the council, and bridging the packages to save a few dataclasses would
trade a boundary for a shortcut.

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
    # One value with the options in order and another reversed: the list decided.
    ORDER_SENSITIVE = "order-sensitive"


class ReadingOrder(Enum):
    """Which order a member read a metric's options in, asked them both ways."""

    IN_ORDER = "in_order"
    REVERSED = "reversed"


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
    # Empty unless the member was also asked the options reversed.
    reversed_prompt_version: str = ""


@dataclass(frozen=True)
class MemberSaid:
    """What one member said about one metric, and who it was.

    `value`, `evidence` and `confidence` are empty for the kinds that have none:
    a member that declined named no value, one that guessed quoted nothing, and
    one that failed said nothing at all. `kind` says which, on every row.
    `order_values` is set for an order-sensitive member alone: the value it gave
    with the options in order, then the one it gave with them reversed.
    `declined_in` names the orders a member asked both ways said NO_EVIDENCE in,
    and `unverified_in` those whose quotation was not found in the advisory; both
    are empty where it was asked once.
    """

    member: MemberIdentity
    kind: SaidKind
    value: str = ""
    evidence: str = ""
    confidence: str = ""
    verified: bool = False
    reason: str = ""
    order_values: tuple[str, ...] = ()
    declined_in: tuple[ReadingOrder, ...] = ()
    unverified_in: tuple[ReadingOrder, ...] = ()


@dataclass(frozen=True)
class MetricEscalation:
    """A metric the council left open, put to the escalation model, and what that model said.

    `prior` is what the council left it as, contested or unresolved. The ruling
    holding this says what came of it: settled on the escalation, or unchanged.
    """

    prior: Outcome
    said: MemberSaid


@dataclass(frozen=True)
class MetricRuling:
    """What the chairman decided about one metric, and what every member said first.

    `escalation` is None where the council settled the metric, and on every
    metric of a run that named no escalation model. `same_evidence_different_reading`
    flags two members whose verified quotations are the same words and whose
    values differ (`council.same_evidence`); it is shown beside the ruling and
    decides nothing.
    """

    metric: str
    outcome: Outcome
    said: tuple[MemberSaid, ...]
    value: str = ""
    basis: str = ""
    confidence: str = ""
    fallback_source: str = ""
    escalation: MetricEscalation | None = None
    same_evidence_different_reading: bool = False


@dataclass(frozen=True)
class CouncilAssessment:
    """A council that settled every metric for one advisory, and the vector it handed over."""

    advisory_id: str
    vector: str
    single_assessor: bool
    rulings: tuple[MetricRuling, ...] = ()
    # Nothing on the vector was cross-checked: the run reached one member, or
    # every basis was "sole", each metric resting on one member's quotation alone
    # though not always the same member's. Worked out in `cli.council_run`, which
    # knows the council's own types, because this package does not import them.
    nothing_cross_checked: bool = False


@dataclass(frozen=True)
class CouncilNotAsked:
    """A finding no council was put to, and why -- which is not no council having run.

    Three facts a reader has to tell apart: a finding the council **was not asked
    about**, which is this; a finding it assessed and could not settle, which is
    `CouncilWithoutVector`; and a run where nobody was named to ask, which is no
    council entry at all. Recording nothing for a finding passed over would report
    the first as the third, and that is false.

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
    is an absence, the first is a result, and what it left open, after any
    escalation, is what the record has to show.
    """

    advisory_id: str
    single_assessor: bool
    unresolved_metrics: tuple[str, ...] = ()
    contested_metrics: tuple[str, ...] = ()
    rulings: tuple[MetricRuling, ...] = ()


CouncilOutcome = CouncilAssessment | CouncilWithoutVector | CouncilNotAsked
