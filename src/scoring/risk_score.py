"""The Organisation Risk Score: four clamped categories, weighted, summed, banded, floored.

Deterministic by construction -- no model, no clock, no randomness, no network.
The same answers give the same number on every machine, and the record keeps
every category **and the weight it carried** beside the total, so somebody can
re-derive the number by hand from the record rather than from this file.

The bands are in `scoring.bands`, and they are the organisation bands rather
than the CVSS ones. The floors in `scoring.floors` are applied here and nowhere
else, to the band and never to the number, from the answers the score was
weighed from; the band the number gives is kept beside the band the floors left.
"""

import math
from dataclasses import dataclass
from itertools import chain
from typing import Mapping

from scoring.bands import risk_band
from scoring.category import CategoryScore
from scoring.floors import AppliedFloor, applied_floors, floored_band
from scoring.question import Answer, Category
from scoring.technical import TechnicalInput, is_technical_unknown, technical_category_score

# The table in `docs/SCORING_MODEL.md`. The source document also prints an inline
# formula of 0.30/0.30/0.20/0.20, which matches neither its own table nor its own
# worked example; the design records that and settles on these.
CATEGORY_WEIGHTS: Mapping[Category, float] = {
    Category.TECHNICAL: 0.30,
    Category.EXPOSURE: 0.25,
    Category.BUSINESS: 0.25,
    Category.THREAT: 0.20,
}

# Every category is at most one decimal and every weight at most two, so two
# decimals is exact for a real assessment and removes only binary-float noise:
# 62x0.30 + 13x0.25 + 38x0.25 + 70x0.20 comes out 45.349999999999994 unrounded.
SCORE_DECIMALS = 2


@dataclass(frozen=True)
class CategoryWeight:
    """What one category was worth in the total, by the name the design gives it."""

    category: str
    weight: float


@dataclass(frozen=True)
class RiskScore:
    """One assessment's Organisation Risk Score, with everything it was derived from."""

    score: float
    band: str
    technical: TechnicalInput
    technical_score: float
    exposure: CategoryScore
    business: CategoryScore
    threat: CategoryScore
    weights: tuple[CategoryWeight, ...]
    is_provisional: bool
    unknown_questions: tuple[str, ...]
    # The band the number gives, before any floor; `band` is the one after them.
    score_band: str
    floors: tuple[AppliedFloor, ...]

    def __post_init__(self) -> None:
        """Refuse a band or a floor that does not follow from the score and the answers here."""
        # As `CategoryScore` holds its clamp: the type holds the floors, so a
        # hand-built record cannot claim a floor its answers do not meet.
        banded = risk_band(self.score)
        floors = applied_floors(banded, answers_of(self.exposure, self.business, self.threat))
        expected = (banded, floors, floored_band(banded, floors))
        if (self.score_band, self.floors, self.band) == expected:
            return
        raise ValueError(
            f"A score of {self.score} bands {banded} and, after its floors, {expected[2]}; "
            f"this record says {self.score_band} and {self.band}"
        )


def organisation_risk_score(
    technical: TechnicalInput,
    exposure: CategoryScore,
    business: CategoryScore,
    threat: CategoryScore,
) -> RiskScore:
    """Weigh the four clamped categories into one 0-100 score for this environment."""
    refuse_wrong_category(exposure, Category.EXPOSURE)
    refuse_wrong_category(business, Category.BUSINESS)
    refuse_wrong_category(threat, Category.THREAT)
    technical_score = technical_category_score(technical)
    score = weighted_total(technical_score, exposure, business, threat)
    unknown = unknown_questions_of(exposure, business, threat)
    floors = applied_floors(risk_band(score), answers_of(exposure, business, threat))
    return RiskScore(
        score=score,
        band=floored_band(risk_band(score), floors),
        technical=technical,
        technical_score=technical_score,
        exposure=exposure,
        business=business,
        threat=threat,
        weights=recorded_weights(),
        is_provisional=bool(unknown) or is_technical_unknown(technical),
        unknown_questions=unknown,
        score_band=risk_band(score),
        floors=floors,
    )


def recorded_weights() -> tuple[CategoryWeight, ...]:
    """Record the weighting that combined the categories, in the design's own order."""
    # On the record and not only in `docs/SCORING_MODEL.md`: every other term of
    # the total is kept, and a reader should not need a second document to
    # finish arithmetic the record otherwise fully supports.
    return tuple(
        CategoryWeight(category.value, weight) for category, weight in CATEGORY_WEIGHTS.items()
    )


def weighted_total(
    technical_score: float,
    exposure: CategoryScore,
    business: CategoryScore,
    threat: CategoryScore,
) -> float:
    """Multiply each already-clamped category by its weight and add them up."""
    weighted = [
        technical_score * CATEGORY_WEIGHTS[Category.TECHNICAL],
        exposure.score * CATEGORY_WEIGHTS[Category.EXPOSURE],
        business.score * CATEGORY_WEIGHTS[Category.BUSINESS],
        threat.score * CATEGORY_WEIGHTS[Category.THREAT],
    ]
    return round(math.fsum(weighted), SCORE_DECIMALS)


def answers_of(*categories: CategoryScore) -> dict[str, Answer]:
    """Give every answer the score was weighed from, by question id, for the floors to read."""
    answered = chain.from_iterable(category.answers for category in categories)
    return {one.question.question_id: one.answer for one in answered}


def unknown_questions_of(*categories: CategoryScore) -> tuple[str, ...]:
    """Name every question answered Unknown, in category then question order."""
    return tuple(chain.from_iterable(category.unknown_questions for category in categories))


def refuse_wrong_category(scored: CategoryScore, expected: Category) -> None:
    """Refuse a category score handed to the wrong slot, which would weigh it wrongly."""
    if not isinstance(scored, CategoryScore):
        raise TypeError(f"{expected.value} must be a CategoryScore, not {type(scored).__name__}")
    if scored.category is expected:
        return
    raise ValueError(f"{scored.category.value} was given where {expected.value} was expected")
