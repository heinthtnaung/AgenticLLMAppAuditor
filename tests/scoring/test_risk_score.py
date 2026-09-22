"""Guards on the Organisation Risk Score: the worked example, the weights, the bands."""

import math

import pytest

from scoring.category import CategoryScore, score_category
from scoring.question import Answer, Category, Question
from scoring.risk_score import CATEGORY_WEIGHTS, organisation_risk_score
from scoring.technical import TechnicalSeverity, UnknownTechnicalSeverity, from_cvss_base_score
from scoring_samples import (
    BUSINESS_QUESTIONS,
    DISABLED,
    EXPOSURE_QUESTIONS,
    EXPLOITED,
    INTERNET_FACING,
    SEGMENTED,
    THREAT_QUESTIONS,
    all_answered,
)

NOTHING_EXPOSED = score_category(Category.EXPOSURE, all_answered(EXPOSURE_QUESTIONS, Answer.NO))
NO_BUSINESS_IMPACT = score_category(Category.BUSINESS, all_answered(BUSINESS_QUESTIONS, Answer.NO))
NO_THREAT = score_category(Category.THREAT, all_answered(THREAT_QUESTIONS, Answer.NO))
BUSINESS_CRITICAL_ASSET = score_category(
    Category.BUSINESS, all_answered(BUSINESS_QUESTIONS, Answer.YES)
)


def one_answer(category: Category, weight: float) -> CategoryScore:
    """Score a category from a single Yes worth exactly what a test needs."""
    question = Question(f"{category.name}-X", "Is it?", category, weight)
    return score_category(category, {question: Answer.YES})


def exposure_answering(question: Question, answer: Answer) -> CategoryScore:
    """Score exposure with every question answered No except one."""
    return score_category(
        Category.EXPOSURE, {**all_answered(EXPOSURE_QUESTIONS, Answer.NO), question: answer}
    )


def scored(technical, exposure=NOTHING_EXPOSED, business=NO_BUSINESS_IMPACT, threat=NO_THREAT):
    """Score one assessment, defaulting every category a test is not about to nothing."""
    return organisation_risk_score(
        technical=technical, exposure=exposure, business=business, threat=threat
    )


def test_the_worked_example_from_the_design_gives_44_medium():
    # docs/SCORING_MODEL.md: CVSS 8.0, no exposure, no threat, business-critical
    # and production and sensitive data. 80x0.30 + 0x0.25 + 80x0.25 + 0x0.20 = 44.
    # The number is the source document's, so this passing means the code agrees
    # with the design and not merely with itself.
    result = scored(from_cvss_base_score(8.0, "ghsa"), business=BUSINESS_CRITICAL_ASSET)
    assert result.score == 44.0
    assert result.band == "Medium"
    assert not result.is_provisional


def test_the_weights_sum_to_one():
    assert math.fsum(CATEGORY_WEIGHTS.values()) == 1.0


def test_the_weights_are_the_ones_the_table_gives_and_not_the_inline_formula():
    # The source document also prints 0.30/0.30/0.20/0.20, which its own worked
    # example contradicts.
    assert CATEGORY_WEIGHTS[Category.TECHNICAL] == 0.30
    assert CATEGORY_WEIGHTS[Category.EXPOSURE] == 0.25
    assert CATEGORY_WEIGHTS[Category.BUSINESS] == 0.25
    assert CATEGORY_WEIGHTS[Category.THREAT] == 0.20


def test_a_clamped_category_contributes_nothing_rather_than_subtracting():
    # Exposure comes to -45 raw. Clamped first it contributes 0 and the score is
    # the worked example's 44; clamped after weighting it would take 11.25 off
    # the other categories and give 32.75.
    controlled = score_category(
        Category.EXPOSURE,
        {
            **all_answered(EXPOSURE_QUESTIONS, Answer.NO),
            SEGMENTED: Answer.YES,
            DISABLED: Answer.YES,
        },
    )
    assert controlled.raw_total == -45
    result = scored(
        from_cvss_base_score(8.0, "ghsa"), exposure=controlled, business=BUSINESS_CRITICAL_ASSET
    )
    assert result.score == 44.0


def test_the_score_is_not_left_carrying_binary_float_noise():
    # 62x0.30 + 13x0.25 + 38x0.25 + 70x0.20 comes to 45.349999999999994 in binary
    # floating point. A score that prints like that cannot be checked by hand
    # against the record, which is the one thing the record is for.
    result = organisation_risk_score(
        technical=TechnicalSeverity(score=62.0, derived_from="operator"),
        exposure=one_answer(Category.EXPOSURE, 13),
        business=one_answer(Category.BUSINESS, 38),
        threat=one_answer(Category.THREAT, 70),
    )
    assert result.score == 45.35


def test_an_unknown_answer_makes_the_whole_score_provisional():
    threat = score_category(
        Category.THREAT, {**all_answered(THREAT_QUESTIONS, Answer.NO), EXPLOITED: Answer.UNKNOWN}
    )
    result = scored(
        from_cvss_base_score(8.0, "ghsa"),
        exposure=exposure_answering(INTERNET_FACING, Answer.UNKNOWN),
        threat=threat,
    )
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


def test_no_source_is_privileged_and_the_one_used_stays_on_the_record():
    from_ghsa = scored(from_cvss_base_score(8.0, "ghsa"))
    from_redhat = scored(from_cvss_base_score(8.0, "redhat"))
    assert from_ghsa.score == from_redhat.score
    assert "ghsa" in from_ghsa.technical.derived_from
    assert "redhat" in from_redhat.technical.derived_from


def test_the_same_answers_always_give_the_same_score():
    first = scored(from_cvss_base_score(8.0, "ghsa"), business=BUSINESS_CRITICAL_ASSET)
    second = scored(from_cvss_base_score(8.0, "ghsa"), business=BUSINESS_CRITICAL_ASSET)
    assert first == second


def test_the_record_keeps_every_category_so_the_score_re_derives():
    result = scored(from_cvss_base_score(8.0, "ghsa"), business=BUSINESS_CRITICAL_ASSET)
    by_hand = math.fsum([
        result.technical_score * CATEGORY_WEIGHTS[Category.TECHNICAL],
        result.exposure.score * CATEGORY_WEIGHTS[Category.EXPOSURE],
        result.business.score * CATEGORY_WEIGHTS[Category.BUSINESS],
        result.threat.score * CATEGORY_WEIGHTS[Category.THREAT],
    ])
    assert round(by_hand, 2) == result.score


@pytest.mark.parametrize(
    ("slot", "wrong"),
    [("exposure", NO_BUSINESS_IMPACT), ("business", NO_THREAT), ("threat", NOTHING_EXPOSED)],
)
def test_a_category_handed_to_the_wrong_slot_is_refused(slot, wrong):
    # Every slot is guarded on its own line, so every slot is tested on its own:
    # deleting one guard left the whole suite green.
    with pytest.raises(ValueError, match="was given where"):
        scored(from_cvss_base_score(8.0, "ghsa"), **{slot: wrong})


@pytest.mark.parametrize("slot", ["exposure", "business", "threat"])
@pytest.mark.parametrize("given", [None, 80.0, "80"], ids=["none", "float", "str"])
def test_a_category_that_is_no_category_score_is_refused(slot, given):
    with pytest.raises(TypeError, match="must be a CategoryScore"):
        scored(from_cvss_base_score(8.0, "ghsa"), **{slot: given})


def test_a_technical_severity_the_caller_computed_itself_is_accepted():
    # The engine never picks a source, so a caller with its own basis says so.
    result = scored(TechnicalSeverity(score=60.0, derived_from="operator override, agreed 2026-09"))
    assert result.score == 18.0
    assert result.band == "Low"
