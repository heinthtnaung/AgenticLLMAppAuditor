"""The human's decision on an assessment: who, what, when, and why.

`docs/SCORING_MODEL.md` keeps the approval record among what is kept per
assessment, and nothing captured one until now.

**Nothing here reads a clock.** The timestamp is part of the human act being
recorded, so it arrives with the act rather than being taken when a report is
rendered -- which is also what keeps the record byte-identical between runs. It
is validated as a real instant so that a record cannot carry `"yesterday"`.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Decision(Enum):
    """What a human did with an assessment."""

    APPROVED = "approved"
    OVERRIDDEN = "overridden"


DECISIONS_BY_WORD = {decision.value: decision for decision in Decision}


@dataclass(frozen=True)
class Approval:
    """One human decision on one audit: who made it, which it was, and when."""

    approver: str
    decision: Decision
    recorded_at: str
    note: str = ""

    def __post_init__(self) -> None:
        """Refuse an approval nobody could be held to."""
        if not self.approver:
            raise ValueError("An approval must name who made it")
        if not isinstance(self.decision, Decision):
            raise TypeError(
                f"An approval is approved or overridden, not {type(self.decision).__name__}"
            )
        refuse_unreal_instant(self.recorded_at)


@dataclass(frozen=True)
class NotApproved:
    """Nobody has approved this audit, which is not the same as nobody having looked."""

    reason: str

    def __post_init__(self) -> None:
        """Refuse an unexplained absence of the record a human is held to."""
        if not self.reason:
            raise ValueError("An absent approval must say why it is absent")


ApprovalOutcome = Approval | NotApproved


def refuse_unreal_instant(recorded_at: str) -> None:
    """Refuse a time that is not one, so a record cannot say 'yesterday'."""
    if not recorded_at:
        raise ValueError("An approval must say when it was made")
    try:
        datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
    except ValueError as fault:
        raise ValueError(f"{recorded_at!r} is not an ISO 8601 instant: {fault}") from fault


def read_decision(word: str) -> Decision:
    """Read the word an operator wrote into the decision it names."""
    decision = DECISIONS_BY_WORD.get(str(word).strip().lower())
    if decision is None:
        allowed = ", ".join(DECISIONS_BY_WORD)
        raise ValueError(f"{word!r} is not a decision; an approval is {allowed}")
    return decision
