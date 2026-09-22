"""Guards on the CVSS Base score: published values, the roundup, and the bands."""

import math

import pytest

from cvss.score import base_score, impact_score, roundup, severity_band
from cvss.vector import differing_metrics, parse

# CVE-2025-37164: one CVE, two published scorings, one metric apart.
CNA_VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
CNA_SCORE = 10.0
TENABLE_VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
TENABLE_SCORE = 9.8

# Scores published by sources other than this repository, cross-checked against
# the FIRST v3.1 specification, section 7.1.
PUBLISHED_SCORES = [
    (CNA_VECTOR, CNA_SCORE),
    (TENABLE_VECTOR, TENABLE_SCORE),
    ("CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H", 8.8),
    ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N", 7.5),
    ("CVSS:3.1/AV:P/AC:H/PR:H/UI:R/S:U/C:L/I:L/A:L", 3.5),
    ("CVSS:3.1/AV:L/AC:H/PR:H/UI:R/S:U/C:N/I:N/A:N", 0.0),
    ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N", 0.0),
]


@pytest.mark.parametrize(("text", "expected"), PUBLISHED_SCORES)
def test_a_published_score_is_reproduced(text, expected):
    assert base_score(parse(text)) == expected


def test_the_same_vector_scores_the_same_every_time():
    vector = parse(TENABLE_VECTOR)
    assert base_score(vector) == base_score(vector) == TENABLE_SCORE


def test_a_version_3_0_vector_scores_as_its_3_1_twin():
    # The Base equations did not change between 3.0 and 3.1.
    assert base_score(parse("CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")) == TENABLE_SCORE


def test_moving_scope_alone_moves_cve_2025_37164_between_its_published_scores():
    tenable = parse(TENABLE_VECTOR)
    cna = tenable.with_metric("S", "C")
    assert differing_metrics(tenable, cna) == ("S",)
    assert base_score(tenable) == TENABLE_SCORE
    assert base_score(cna) == CNA_SCORE


def test_the_scope_changed_equation_is_not_the_unchanged_one():
    # Fails if Impact uses 6.42 x ISCBase for a changed scope, or if the 1.08
    # multiplier is dropped: either way this vector scores 9.8, not 10.0.
    assert base_score(parse(CNA_VECTOR)) == CNA_SCORE
    assert base_score(parse(CNA_VECTOR)) != base_score(parse(TENABLE_VECTOR))


def test_the_scope_changed_impact_keeps_its_penalty_term():
    # Dropping `- 3.25 x (ISCBase - 0.02)^15` scores this vector 10.0.
    assert base_score(parse("CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:H/I:H/A:H")) == 9.6


def test_privileges_required_weighs_more_when_scope_changed():
    unchanged = parse("CVSS:3.1/AV:N/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:H")
    changed = unchanged.with_metric("S", "C")
    assert base_score(unchanged) == 7.2
    assert base_score(changed) == 9.1


@pytest.mark.parametrize(
    "text",
    [
        "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N",
        "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:N/I:N/A:N",
    ],
    ids=["scope unchanged", "scope changed"],
)
def test_zero_impact_is_zero_score_however_exploitable(text):
    # The most reachable weakness there is. Without the guard these score 3.9
    # and 4.0 -- a Medium finding built entirely out of exploitability.
    assert base_score(parse(text)) == 0.0


def test_a_negative_scope_changed_impact_never_rounds_up_into_a_score():
    vector = parse("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:N/I:N/A:N")
    assert impact_score(vector) < 0.0
    assert base_score(vector) == 0.0


def test_the_roundup_is_the_specification_integer_method_not_ceil():
    # The value the specification warns about by name. `math.ceil(x * 10) / 10`
    # returns 8.7 here, which is a different severity band's neighbour and the
    # reason the specification spells the roundup out in integers.
    imprecise_eight_point_six = math.nextafter(8.6, math.inf)
    assert math.ceil(imprecise_eight_point_six * 10) / 10 == 8.7
    assert roundup(imprecise_eight_point_six) == 8.6


@pytest.mark.parametrize("tenth", range(0, 101))
def test_a_value_already_at_one_decimal_is_left_alone(tenth):
    assert roundup(tenth / 10) == tenth / 10


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.0, 0.0), (0.01, 0.1), (0.000001, 0.0), (4.001, 4.1), (8.95, 9.0), (9.99, 10.0)],
)
def test_a_value_below_one_decimal_rounds_up(value, expected):
    assert roundup(value) == expected


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (10.0, "Critical"),
        (9.0, "Critical"),
        (8.9, "High"),
        (7.0, "High"),
        (6.9, "Medium"),
        (4.0, "Medium"),
        (3.9, "Low"),
        (0.1, "Low"),
        (0.0, "None"),
    ],
)
def test_a_score_lands_in_its_band(score, expected):
    assert severity_band(score) == expected


@pytest.mark.parametrize(
    ("lower", "upper", "lower_band", "upper_band"),
    [
        (8.9, 9.0, "High", "Critical"),
        (6.9, 7.0, "Medium", "High"),
        (3.9, 4.0, "Low", "Medium"),
        (0.0, 0.1, "None", "Low"),
    ],
)
def test_both_sides_of_a_band_boundary_land_apart(lower, upper, lower_band, upper_band):
    assert severity_band(lower) == lower_band
    assert severity_band(upper) == upper_band


@pytest.mark.parametrize(
    "score",
    [-0.1, 10.1, 100.0, float("nan"), float("inf")],
    ids=["below zero", "just over ten", "far over ten", "nan", "infinity"],
)
def test_a_number_off_the_scale_is_refused_rather_than_banded(score):
    with pytest.raises(ValueError, match="the scale runs 0.0 to 10.0"):
        severity_band(score)


def test_every_published_score_bands_without_complaint():
    banded = [severity_band(base_score(parse(text))) for text, _ in PUBLISHED_SCORES]
    assert banded == ["Critical", "Critical", "High", "High", "Low", "None", "None"]
