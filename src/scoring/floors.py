"""The severity floors: a band an answer can raise, whatever the weighted total came to.

A weighted total averages, and some facts should not be averaged away. A
vulnerability exploited in the wild on an asset nobody exposes still comes out
Medium or Low by the weights alone, so these rules set the band it may not fall
below. They are the operator's rules, chosen, not measured.

**Only the band moves.** The Organisation Risk Score is the number the weights
give and stays that number; a floor raises the band beside it, and every floor
that did is recorded with its rule, the band before and the band after, so the
number and the band both re-derive from the record.

**Only an explicit Yes triggers one.** Unknown already flags the score
provisional; letting it raise a band as well would read a guess as a fact, and
N/A says the question does not apply. **A floor never lowers a band**: one
already at or above the floor is left where it is, and nothing is recorded.
"""

from dataclasses import dataclass
from typing import Mapping

from scoring.bands import RISK_BANDS
from scoring.library import question
from scoring.question import Answer

# Lowest first, so a higher rank is a more severe band; read off the bands themselves.
BAND_RANK: Mapping[str, int] = {name: rank for rank, (_, name) in enumerate(reversed(RISK_BANDS))}


@dataclass(frozen=True)
class SeverityFloor:
    """One rule: the questions an explicit Yes to all of must meet, the band it sets, and why."""

    rule_id: str
    answered_yes: tuple[str, ...]
    floor_band: str
    reason: str

    def __post_init__(self) -> None:
        """Refuse a rule that names a question nobody approved or a band the scale lacks."""
        if not self.rule_id or not self.answered_yes or not self.reason:
            raise ValueError("A severity floor needs an id, the answers it reads, and its reason")
        for identifier in self.answered_yes:
            question(identifier)
        if self.floor_band not in BAND_RANK:
            raise ValueError(f"{self.rule_id}: {self.floor_band!r} is no organisation band")


@dataclass(frozen=True)
class AppliedFloor:
    """One floor that raised a band: which rule, the answers that met it, and both bands."""

    rule_id: str
    answered_yes: tuple[str, ...]
    band_before: str
    band_after: str


# In ascending order of the band each sets, so a band raised by the first can be
# raised again by the second and both steps are on the record.
SEVERITY_FLOORS: tuple[SeverityFloor, ...] = (
    SeverityFloor(
        "FLOOR-EXPLOITED-HIGH",
        ("THR-1",),
        "High",
        "a vulnerability exploited in the wild is being used against somebody now, "
        "and no weighting of this environment should put it below High",
    ),
    SeverityFloor(
        "FLOOR-EXPLOITED-EXPOSED-CRITICAL",
        ("THR-1", "EXP-1", "BUS-1"),
        "Critical",
        "exploited in the wild, on an internet-facing service, on a business-critical "
        "asset is the case this score exists to catch, and it is Critical",
    ),
)


def applied_floors(band: str, answers: Mapping[str, Answer]) -> tuple[AppliedFloor, ...]:
    """Raise a band by every floor its answers meet, in order, recording each that raised it."""
    applied = []
    for rule in SEVERITY_FLOORS:
        if not meets(rule, answers) or BAND_RANK[rule.floor_band] <= BAND_RANK[band]:
            continue
        applied.append(AppliedFloor(rule.rule_id, rule.answered_yes, band, rule.floor_band))
        band = rule.floor_band
    return tuple(applied)


def meets(rule: SeverityFloor, answers: Mapping[str, Answer]) -> bool:
    """Say whether every question the rule reads was answered an explicit Yes."""
    # An unanswered question is not a Yes, like Unknown and N/A.
    return all(answers.get(identifier) is Answer.YES for identifier in rule.answered_yes)


def floored_band(score_band: str, floors: tuple[AppliedFloor, ...]) -> str:
    """Give the band after its floors: the last one raised it, or none did and it stands."""
    return floors[-1].band_after if floors else score_band
