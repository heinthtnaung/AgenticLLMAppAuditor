"""Guards on the floors inside the engine: the number stays, the band rises, and both are kept."""

from dataclasses import replace

import pytest

from risk_score_samples import no_except, scored
from scoring.question import Answer, Category
from scoring.technical import from_cvss_base_score
from scoring_samples import (
    BUSINESS_CRITICAL,
    BUSINESS_QUESTIONS,
    EXPLOITED,
    EXPOSURE_QUESTIONS,
    INTERNET_FACING,
    THREAT_QUESTIONS,
)

CVSS_5_0 = from_cvss_base_score(5.0, "ghsa")


def exploited(answer: Answer = Answer.YES):
    """Score the threat category with THR-1 answered as given and the rest No."""
    return no_except(Category.THREAT, THREAT_QUESTIONS, {EXPLOITED: answer})


def exposed_and_critical():
    """Score CVSS 5.0 exploited in the wild, internet-facing, on a business-critical asset."""
    return scored(
        CVSS_5_0,
        exposure=no_except(Category.EXPOSURE, EXPOSURE_QUESTIONS, {INTERNET_FACING: Answer.YES}),
        business=no_except(Category.BUSINESS, BUSINESS_QUESTIONS, {BUSINESS_CRITICAL: Answer.YES}),
        threat=exploited(),
    )


def test_a_floor_raises_the_band_and_leaves_the_number_it_was_weighed_to():
    # 50x0.30 + 0 + 0 + 50x0.20 = 25, which bands Medium; exploited, it is High.
    result = scored(CVSS_5_0, threat=exploited())
    assert (result.score, result.score_band, result.band) == (25.0, "Medium", "High")
    assert [one.rule_id for one in result.floors] == ["FLOOR-EXPLOITED-HIGH"]


def test_the_critical_floor_is_reached_from_the_answers_the_score_was_weighed_from():
    # 15 + 40x0.25 + 40x0.25 + 10 = 45 Medium, raised to High and then to Critical.
    result = exposed_and_critical()
    assert (result.score, result.score_band, result.band) == (45.0, "Medium", "Critical")
    steps = [(one.band_before, one.band_after) for one in result.floors]
    assert steps == [("Medium", "High"), ("High", "Critical")]


def test_an_unknown_exploitation_answer_raises_nothing_and_leaves_the_score_provisional():
    result = scored(CVSS_5_0, threat=exploited(Answer.UNKNOWN))
    assert (result.band, result.floors) == ("Low", ())
    assert result.is_provisional


def test_a_score_no_floor_applies_to_keeps_one_band_twice():
    result = scored(CVSS_5_0)
    assert (result.score_band, result.band, result.floors) == ("Low", "Low", ())


@pytest.mark.parametrize("changed", [
    {"floors": (), "band": "Medium"},
    {"band": "High"},
    {"score_band": "High"},
], ids=["floor dropped", "band not the floors'", "score band not the number's"])
def test_a_record_whose_bands_do_not_follow_from_its_score_and_answers_is_refused(changed):
    with pytest.raises(ValueError, match="bands Medium and, after its floors, Critical"):
        replace(exposed_and_critical(), **changed)
