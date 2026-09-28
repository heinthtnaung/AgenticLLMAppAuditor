"""The findings a council was not put to, grouped by why, once for every rendering.

A scoped run assesses the findings whose sources do not settle them, and a record
that dropped the rest would say no council had run on them. So each skip keeps
its reason (`report.council_record.CouncilNotAsked`), and the renderings list them
by reason and by id from the one grouping here.
"""

from dataclasses import dataclass
from typing import Sequence

from report.council_record import CouncilNotAsked


@dataclass(frozen=True)
class PassedOver:
    """One reason the council was not put to some findings, and which findings they were."""

    because: str
    advisory_ids: tuple[str, ...]


def grouped_by_reason(passed: Sequence[CouncilNotAsked]) -> tuple[PassedOver, ...]:
    """Group the findings the council was not put to by the reason it was not put to them."""
    # Grouped once for every rendering rather than in each: three renderings
    # grouping one list three ways is three chances to group it differently.
    reasons = sorted({one.because for one in passed})
    return tuple(PassedOver(one, named_for(one, passed)) for one in reasons)


def named_for(because: str, passed: Sequence[CouncilNotAsked]) -> tuple[str, ...]:
    """Name every finding passed over for one reason, in the order the record holds them."""
    return tuple(one.advisory_id for one in passed if one.because == because)
