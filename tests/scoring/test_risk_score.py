"""Guards on the Organisation Risk Score: the worked example, the weights, the bands."""

import math

from scoring.category import CategoryScore, score_category
from scoring.question import Answer, Category, Question
from scoring.risk_score import CATEGORY_WEIGHTS, RiskScore, organisation_risk_score
from scoring.technical import TechnicalSeverity, from_cvss_base_score
from scoring_samples import DISABLED, EXPOSURE_QUESTIONS, SEGMENTED
from risk_score_samples import BUSINESS_CRITICAL_ASSET, no_except, scored


def one_answer(category: Category, weight: float) -> CategoryScore:
    """Score a category from a single Yes worth exactly what a test needs."""
    question = Question(f"{category.name}-X", "Is it?", category, weight)
    return score_category(category, {question: Answer.YES})


def no_category_zero() -> RiskScore:
    """Score an assessment where every category is non-zero, so every weight moves the total."""
    return organisation_risk_score(
        technical=TechnicalSeverity(score=62.0, derived_from="operator"),
        exposure=one_answer(Category.EXPOSURE, 13),
        business=one_answer(Category.BUSINESS, 38),
        threat=one_answer(Category.THREAT, 70),
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


def test_the_score_carries_the_weighting_that_produced_it():
    # A score nobody can re-derive is not a score. Every other term of the total
    # is on the record, so the weighting is too, rather than only in the design.
    result = scored(from_cvss_base_score(8.0, "ghsa"), business=BUSINESS_CRITICAL_ASSET)
    assert [(one.category, one.weight) for one in result.weights] == [
        ("Technical severity", 0.30),
        ("Exposure and reachability", 0.25),
        ("Business impact", 0.25),
        ("Threat and exploitation", 0.20),
    ]


def test_the_recorded_weighting_re_derives_the_recorded_score():
    # The total follows from the record alone, each weight paired with its
    # category by name, and no category is zero, so no weight goes unchecked.
    result = no_category_zero()
    weight = {one.category: one.weight for one in result.weights}
    by_hand = math.fsum([
        result.technical_score * weight[Category.TECHNICAL.value],
        result.exposure.score * weight[Category.EXPOSURE.value],
        result.business.score * weight[Category.BUSINESS.value],
        result.threat.score * weight[Category.THREAT.value],
    ])
    assert round(by_hand, 2) == result.score


def test_a_clamped_category_contributes_nothing_rather_than_subtracting():
    # Exposure comes to -45 raw. Clamped first it contributes 0 and the score is
    # the worked example's 44; clamped after weighting it would take 11.25 off
    # the other categories and give 32.75.
    isolated = {SEGMENTED: Answer.YES, DISABLED: Answer.YES}
    controlled = no_except(Category.EXPOSURE, EXPOSURE_QUESTIONS, isolated)
    assert controlled.raw_total == -45
    result = scored(
        from_cvss_base_score(8.0, "ghsa"), exposure=controlled, business=BUSINESS_CRITICAL_ASSET
    )
    assert result.score == 44.0


def test_the_score_is_not_left_carrying_binary_float_noise():
    # 62x0.30 + 13x0.25 + 38x0.25 + 70x0.20 comes to 45.349999999999994 in binary
    # floating point. A score that prints like that cannot be checked by hand
    # against the record, which is the one thing the record is for.
    assert no_category_zero().score == 45.35


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


def test_a_technical_severity_the_caller_computed_itself_is_accepted():
    # The engine never picks a source, so a caller with its own basis says so.
    result = scored(TechnicalSeverity(score=60.0, derived_from="operator override, agreed 2026-09"))
    assert result.score == 18.0
    assert result.band == "Low"
