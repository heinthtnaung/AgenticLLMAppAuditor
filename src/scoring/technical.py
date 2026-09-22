"""The technical severity category, supplied by the caller rather than chosen here.

A finding carries several source-attributed scores that disagree, and
`docs/SCORING_MODEL.md` leaves open which source wins: settling that is the
assessor council's job and the council does not exist. So this engine never
reaches into a finding and picks one. The caller supplies the number and says
where it came from, and **the provenance is required, not optional** -- an
unattributed technical score is the merge the design forbids arriving by the
back door, and on the repository under test a rule of "use NVD" would have
nothing to read on 14 findings in 18.

Nobody having scored a finding is its own answer and not a score of zero, so it
is its own type, the way `src/findings/assessment.py` keeps an unreadable source
apart from a readable one.
"""

import math
from dataclasses import dataclass

from scoring.scale import MAXIMUM_CATEGORY_SCORE, MINIMUM_CATEGORY_SCORE

CVSS_TO_CATEGORY_SCALE = 10.0
MINIMUM_BASE_SCORE = 0.0
MAXIMUM_BASE_SCORE = 10.0


@dataclass(frozen=True)
class TechnicalSeverity:
    """A technical category score on the 0-100 scale, and where the caller got it."""

    score: float
    derived_from: str

    def __post_init__(self) -> None:
        """Refuse a score off the scale, or one that names no origin."""
        if not self.derived_from:
            raise ValueError("A technical severity must say where it came from")
        if not math.isfinite(self.score):
            raise ValueError(f"{self.score!r} is no technical severity")
        if not MINIMUM_CATEGORY_SCORE <= self.score <= MAXIMUM_CATEGORY_SCORE:
            raise ValueError(f"A technical severity runs 0 to 100, not {self.score!r}")


@dataclass(frozen=True)
class UnknownTechnicalSeverity:
    """Nobody scored this finding, which is not the same as scoring it zero."""

    reason: str

    def __post_init__(self) -> None:
        """Refuse an unexplained absence, which reads on a report as an oversight."""
        if not self.reason:
            raise ValueError("An unknown technical severity must say why it is unknown")


TechnicalInput = TechnicalSeverity | UnknownTechnicalSeverity


def technical_category_score(technical: TechnicalInput) -> float:
    """Give what the technical category contributes, which is nothing when nobody scored it."""
    if is_technical_unknown(technical):
        return MINIMUM_CATEGORY_SCORE
    return technical.score


def is_technical_unknown(technical: TechnicalInput) -> bool:
    """Say whether no source scored this finding, which makes the whole score provisional."""
    if isinstance(technical, UnknownTechnicalSeverity):
        return True
    if isinstance(technical, TechnicalSeverity):
        return False
    raise TypeError(
        f"Technical severity must be a TechnicalSeverity or an UnknownTechnicalSeverity, "
        f"not {type(technical).__name__}"
    )


def from_cvss_base_score(base_score: float, source: str) -> TechnicalSeverity:
    """Put one named source's CVSS base score on the 0-100 category scale."""
    if not source:
        raise ValueError("A CVSS base score must be attributed to the source that published it")
    if not math.isfinite(base_score) or not MINIMUM_BASE_SCORE <= base_score <= MAXIMUM_BASE_SCORE:
        raise ValueError(f"{base_score!r} is not a CVSS base score; the scale runs 0.0 to 10.0")
    return TechnicalSeverity(
        score=base_score * CVSS_TO_CATEGORY_SCALE,
        derived_from=f"{source} CVSS base score {base_score}",
    )
