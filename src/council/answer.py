"""What one member returns about one metric, and who returned it.

This is the contract the model-facing half parses replies into. Nothing here
calls a model; it is the shape an answer has to be in before the chairman will
look at it, and an answer that cannot be constructed is one no reply produced.

Three replies, three types, because a member can do three different things and
the record has to tell them apart.

`MemberAnswer` is a value with a quotation behind it. `MemberFoundNoEvidence` is
an honest absence -- `docs/COUNCIL.md` makes that a result that must survive to
the report, since some advisories carry no evidence for some metrics and no
reader could settle them. `MemberGuessed` is a value with nothing behind it,
which is the thing that file tells a member not to do: "a member that cannot
find supporting text must say so rather than guess."

The last two carry exactly the same weight, which is none. What separates them
is not arithmetic: an absence is a fact about the **advisory**, and a guess is a
fact about the **member** -- one that can be counted per member across a corpus,
and one that is unrecoverable if it is folded into the absence.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from cvss.metrics import METRIC_ORDER, refuse_illegal_pair


class Confidence(Enum):
    """How sure a member is of the value it supports."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Weakest first. A ruling is worth what the least certain of the answers behind
# it is worth, so the chairman reads this order rather than averaging anything.
CONFIDENCE_ORDER: tuple[Confidence, ...] = (Confidence.LOW, Confidence.MEDIUM, Confidence.HIGH)


@dataclass(frozen=True)
class MemberIdentity:
    """Which member answered, what it was, and whether the text left this machine."""

    name: str
    provider: str
    model: str
    family: str
    ran_local: bool
    prompt_version: str

    def __post_init__(self) -> None:
        """Refuse an identity a reader could not reconstruct the run from."""
        missing = [
            field
            for field in ("name", "provider", "model", "family", "prompt_version")
            if not getattr(self, field)
        ]
        if missing:
            raise ValueError(f"A member identity needs {', '.join(missing)}")
        if not isinstance(self.ran_local, bool):
            raise TypeError(
                f"{self.name!r} must say whether it ran local, not {type(self.ran_local).__name__}"
            )


@dataclass(frozen=True)
class MemberAnswer:
    """One member's value for one metric, and the quotation it says supports it."""

    metric: str
    value: str
    evidence: str
    confidence: Confidence
    member: MemberIdentity

    def __post_init__(self) -> None:
        """Refuse an answer naming no real metric, no legal value, or no quotation."""
        # The vocabulary is `cvss.metrics` and is not restated here: the parser,
        # the equations and the council agree on it by construction or not at all.
        refuse_illegal_pair(self.metric, self.value)
        if not self.evidence.strip():
            raise ValueError(f"{self.metric} was answered with no quotation at all")
        if not isinstance(self.confidence, Confidence):
            raise TypeError(
                f"{self.metric} needs a Confidence, not {type(self.confidence).__name__}"
            )
        refuse_unnamed_member(self.metric, self.member)


@dataclass(frozen=True)
class MemberFoundNoEvidence:
    """One member reporting that the advisory says nothing about a metric."""

    metric: str
    member: MemberIdentity

    def __post_init__(self) -> None:
        """Refuse an absence that names no real metric or no member."""
        if self.metric not in METRIC_ORDER:
            raise ValueError(
                f"{self.metric!r} is not a CVSS Base metric; "
                f"the eight are {', '.join(METRIC_ORDER)}"
            )
        refuse_unnamed_member(self.metric, self.member)


@dataclass(frozen=True)
class MemberGuessed:
    """One member offering a value it could not quote the advisory in support of."""

    metric: str
    value: str
    member: MemberIdentity

    def __post_init__(self) -> None:
        """Refuse a guess that is not even a legal reading of the metric."""
        # The value is kept and validated although it can never move a number:
        # what it is worth is zero, what it records is which way that member
        # leaned when it had nothing to go on.
        refuse_illegal_pair(self.metric, self.value)
        refuse_unnamed_member(self.metric, self.member)


MemberReply = MemberAnswer | MemberFoundNoEvidence | MemberGuessed


def refuse_unnamed_member(metric: str, member: object) -> None:
    """Refuse a reply that does not say which member gave it."""
    if isinstance(member, MemberIdentity):
        return
    raise TypeError(
        f"{metric} must name the member that replied, not {type(member).__name__}"
    )


def weakest_confidence(answers: Iterable[MemberAnswer]) -> Confidence:
    """Give the least certain confidence among several answers, refusing none at all."""
    confidences = [answer.confidence for answer in answers]
    if not confidences:
        raise ValueError("No answers to take a confidence from")
    return min(confidences, key=CONFIDENCE_ORDER.index)
