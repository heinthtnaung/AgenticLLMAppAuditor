"""Guards on a score resting on an unknown: carried and flagged provisional, never read as No."""

from scoring.category import score_category
from scoring.question import Answer, Category
from scoring.technical import UnknownTechnicalSeverity, from_cvss_base_score
from scoring_samples import (
    EXPLOITED, EXPOSURE_QUESTIONS, INTERNET_FACING, THREAT_QUESTIONS, all_answered,
)
from risk_score_samples import BUSINESS_CRITICAL_ASSET, no_except, scored


def test_an_unknown_answer_makes_the_whole_score_provisional():
    exposure = no_except(Category.EXPOSURE, EXPOSURE_QUESTIONS, {INTERNET_FACING: Answer.UNKNOWN})
    threat = no_except(Category.THREAT, THREAT_QUESTIONS, {EXPLOITED: Answer.UNKNOWN})
    result = scored(from_cvss_base_score(8.0, "ghsa"), exposure=exposure, threat=threat)
    assert result.is_provisional
    assert result.unknown_questions == ("EXP-1", "THR-1")


def test_an_unknown_answer_is_still_scored_rather_than_refused():
    exposure = score_category(Category.EXPOSURE, all_answered(EXPOSURE_QUESTIONS, Answer.UNKNOWN))
    result = scored(from_cvss_base_score(8.0, "ghsa"), exposure=exposure)
    assert result.score == 24.0
    assert result.is_provisional


def test_not_applicable_answers_leave_the_score_settled():
    exposure = score_category(
        Category.EXPOSURE, all_answered(EXPOSURE_QUESTIONS, Answer.NOT_APPLICABLE)
    )
    result = scored(from_cvss_base_score(8.0, "ghsa"), exposure=exposure)
    assert not result.is_provisional
    assert result.unknown_questions == ()


def test_a_finding_nobody_scored_is_provisional_and_not_a_zero_assessment():
    unknown = UnknownTechnicalSeverity(reason="no source published a v3 vector")
    result = scored(unknown, business=BUSINESS_CRITICAL_ASSET)
    assert result.technical_score == 0.0
    assert result.is_provisional
    assert result.technical is unknown


def test_an_unknown_technical_severity_is_told_apart_from_one_scored_zero():
    unknown = scored(UnknownTechnicalSeverity(reason="no v3 vector"))
    zero = scored(from_cvss_base_score(0.0, "ghsa"))
    assert unknown.score == zero.score == 0.0
    assert unknown.is_provisional
    assert not zero.is_provisional
