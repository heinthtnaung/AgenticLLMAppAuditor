"""Guards on the organisation bands, which are not the CVSS bands."""

import pytest

from cvss.score import severity_band
from scoring.bands import RISK_BANDS, risk_band
from scoring.category import score_category
from scoring.question import Answer, Category
from scoring.risk_score import organisation_risk_score
from scoring.technical import from_cvss_base_score
from scoring_samples import (
    BUSINESS_QUESTIONS,
    EXPOSURE_QUESTIONS,
    THREAT_QUESTIONS,
    all_answered,
)


def nothing_answered(questions, category):
    """Score a category whose every question was answered No."""
    return score_category(category, all_answered(questions, Answer.NO))


@pytest.mark.parametrize(
    ("score", "expected"),
    [(0.0, "Low"), (24.0, "Low"), (25.0, "Medium"), (49.0, "Medium"),
     (50.0, "High"), (74.0, "High"), (75.0, "Critical"), (100.0, "Critical")],
)
def test_a_score_lands_in_its_organisation_band(score, expected):
    assert risk_band(score) == expected


@pytest.mark.parametrize(
    ("lower", "upper", "lower_band", "upper_band"),
    [
        (24.0, 25.0, "Low", "Medium"),
        (49.0, 50.0, "Medium", "High"),
        (74.0, 75.0, "High", "Critical"),
    ],
)
def test_both_sides_of_a_band_boundary_land_apart(lower, upper, lower_band, upper_band):
    assert risk_band(lower) == lower_band
    assert risk_band(upper) == upper_band


@pytest.mark.parametrize(
    "score",
    [-0.1, 100.1, 1000.0, float("nan"), float("inf")],
    ids=["below", "just above", "far above", "nan", "infinity"],
)
def test_a_number_off_the_organisation_scale_is_refused(score):
    with pytest.raises(ValueError, match="the scale runs 0 to 100"):
        risk_band(score)


def test_the_bands_are_the_four_the_design_names():
    assert [name for _, name in RISK_BANDS] == ["Critical", "High", "Medium", "Low"]


@pytest.mark.parametrize(
    ("score", "organisation", "cvss"),
    [(0.0, "Low", "None"), (25.0, "Medium", "Low"), (50.0, "High", "Medium"),
     (75.0, "Critical", "High")],
)
def test_the_two_scales_put_their_boundaries_in_different_places(score, organisation, cvss):
    # Every organisation boundary falls inside a CVSS band rather than on its
    # edge, so the two functions are deliberately separate. They do agree on
    # some scores -- 90 is Critical on both -- and that is not the same thing as
    # being one scale.
    assert risk_band(score) == organisation
    assert severity_band(score / 10) == cvss


def test_the_organisation_scale_reaches_past_where_cvss_stops():
    # 100 is a valid organisation score and no CVSS score at all.
    assert risk_band(100.0) == "Critical"
    with pytest.raises(ValueError):
        severity_band(100.0)


@pytest.mark.parametrize(
    ("base_score", "expected_score", "expected_band"),
    [(9.8, 29.4, "Medium"), (7.5, 22.5, "Low")],
    ids=["cvss critical, organisation medium", "cvss high, organisation low"],
)
def test_the_two_scales_band_one_finding_differently(base_score, expected_score, expected_band):
    # This is the point of the exercise, not a disagreement to reconcile: the
    # CVSS band is the published technical severity, the organisation band is
    # what that severity is worth in this environment.
    result = organisation_risk_score(
        technical=from_cvss_base_score(base_score, "ghsa"),
        exposure=nothing_answered(EXPOSURE_QUESTIONS, Category.EXPOSURE),
        business=nothing_answered(BUSINESS_QUESTIONS, Category.BUSINESS),
        threat=nothing_answered(THREAT_QUESTIONS, Category.THREAT),
    )
    assert result.score == expected_score
    assert result.band == expected_band
    assert severity_band(base_score) != result.band
