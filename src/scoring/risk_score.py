"""The Organisation Risk Score: four clamped categories, weighted, summed, banded.

Deterministic by construction -- no model, no clock, no randomness, no network.
The same answers give the same number on every machine, and the record keeps
every category **and the weight it carried** beside the total, so somebody can
re-derive the number by hand from the record rather than from this file.

The bands are in `scoring.bands`, and they are the organisation bands rather
than the CVSS ones.
"""

import math
from dataclasses import dataclass
from itertools import chain
from typing import Mapping

from scoring.bands import risk_band
from scoring.category import CategoryScore
from scoring.question import Category
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
    return RiskScore(
        score=score,
        band=risk_band(score),
        technical=technical,
        technical_score=technical_score,
        exposure=exposure,
        business=business,
        threat=threat,
        weights=recorded_weights(),
        is_provisional=bool(unknown) or is_technical_unknown(technical),
        unknown_questions=unknown,
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
