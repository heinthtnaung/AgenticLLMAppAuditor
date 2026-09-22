"""Guards on the technical category input: attributed, on scale, or honestly unknown."""

import pytest

from scoring.technical import (
    TechnicalSeverity,
    UnknownTechnicalSeverity,
    from_cvss_base_score,
    is_technical_unknown,
    technical_category_score,
)


def test_a_cvss_base_score_goes_onto_the_0_to_100_scale():
    technical = from_cvss_base_score(8.0, "ghsa")
    assert technical.score == 80.0
    assert technical.derived_from == "ghsa CVSS base score 8.0"


@pytest.mark.parametrize(
    ("base_score", "expected"), [(0.0, 0.0), (3.5, 35.0), (9.8, 98.0), (10.0, 100.0)]
)
def test_the_scale_is_exact_at_one_decimal(base_score, expected):
    assert from_cvss_base_score(base_score, "nvd").score == expected


def test_the_source_is_named_on_the_record():
    # No source is privileged anywhere in this engine, so the one the caller
    # chose has to be readable off the score afterwards.
    assert "redhat" in from_cvss_base_score(7.5, "redhat").derived_from


def test_a_base_score_with_no_source_is_refused():
    with pytest.raises(ValueError, match="must be attributed to the source"):
        from_cvss_base_score(8.0, "")


@pytest.mark.parametrize(
    "base_score", [-0.1, 10.1, float("nan"), float("inf")], ids=["below", "above", "nan", "inf"]
)
def test_a_base_score_off_the_cvss_scale_is_refused(base_score):
    with pytest.raises(ValueError, match="not a CVSS base score"):
        from_cvss_base_score(base_score, "ghsa")


def test_a_technical_severity_with_no_origin_is_refused():
    with pytest.raises(ValueError, match="must say where it came from"):
        TechnicalSeverity(score=80.0, derived_from="")


@pytest.mark.parametrize("score", [-1.0, 101.0], ids=["below", "above"])
def test_a_technical_severity_off_the_category_scale_is_refused(score):
    with pytest.raises(ValueError, match="runs 0 to 100"):
        TechnicalSeverity(score=score, derived_from="operator")


def test_an_unknown_technical_severity_must_say_why():
    with pytest.raises(ValueError, match="must say why it is unknown"):
        UnknownTechnicalSeverity(reason="")


def test_an_unknown_technical_severity_is_not_a_score_of_zero():
    unknown = UnknownTechnicalSeverity(reason="no source published a v3 vector")
    assert not isinstance(unknown, TechnicalSeverity)
    assert not hasattr(unknown, "score")


def test_a_scored_finding_contributes_its_own_number():
    assert technical_category_score(from_cvss_base_score(8.0, "ghsa")) == 80.0
    assert not is_technical_unknown(from_cvss_base_score(8.0, "ghsa"))


def test_an_unscored_finding_contributes_nothing_and_is_known_to_be_unknown():
    unknown = UnknownTechnicalSeverity(reason="no source published a v3 vector")
    assert technical_category_score(unknown) == 0.0
    assert is_technical_unknown(unknown)


@pytest.mark.parametrize("given", [None, 80.0, "ghsa 8.0"], ids=["none", "float", "str"])
def test_something_that_is_neither_kind_of_technical_severity_is_refused(given):
    with pytest.raises(TypeError, match="must be a TechnicalSeverity or an Unknown"):
        technical_category_score(given)
