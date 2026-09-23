"""Guards on what this environment makes of a finding, scored once per source."""

import pytest

from organisation.risk import assess, from_council, per_source
from organisation_samples import (
    CVSS_8_0,
    HIGH_HIGH,
    HIGH_LOW,
    LOW_CONFIDENTIALITY,
    ON_THE_BOUNDARY,
    TOTAL_LOSS,
    WORKED_EXAMPLE_ANSWERS,
    finding,
)
from scoring.question import Answer
from scoring.technical import UnknownTechnicalSeverity


def weighed(answers=None, **vectors):
    """Score one finding against an environment, once per source it carries."""
    given = WORKED_EXAMPLE_ANSWERS if answers is None else answers
    one = finding(**vectors)
    return assess(one, given, per_source(one))


def test_the_worked_example_from_the_design_gives_44_medium():
    # docs/SCORING_MODEL.md end to end, now through the approved library: CVSS
    # 8.0, no exposure, no threat, business-critical and production and
    # sensitive data. 80x0.30 + 0x0.25 + 80x0.25 + 0x0.20 = 44. The number is
    # the source document's, so this passing means the library's weights agree
    # with the design and not merely with themselves.
    risk = weighed(ghsa=CVSS_8_0)
    assert [one.score for one in risk.scores] == [44.0]
    assert risk.bands == ("Medium",)
    assert not risk.is_provisional


def test_a_finding_is_scored_once_for_every_source_that_scored_it():
    # No source is chosen between, because choosing one is the precedence the
    # design leaves open.
    risk = weighed(ghsa=TOTAL_LOSS, nvd=LOW_CONFIDENTIALITY)
    assert len(risk.scores) == 2
    assert [one.technical.derived_from for one in risk.scores] == [
        "ghsa CVSS base score 9.8",
        "nvd CVSS base score 5.3",
    ]


def test_a_cvss_disagreement_can_stop_mattering_once_the_environment_is_weighed():
    # 5.3 against 9.8 is Medium against Critical on the published scale. In an
    # environment with nothing exposed they are the same organisation band, and
    # that is a result: the argument does not change what to do here.
    risk = weighed(ghsa=TOTAL_LOSS, nvd=LOW_CONFIDENTIALITY)
    assert not risk.band_depends_on_the_source
    assert risk.bands == ("Medium",)


def test_a_cvss_agreement_can_start_mattering_once_the_environment_is_weighed():
    # 7.0 and 7.5 are both High on the published scale and land either side of
    # the Low/Medium boundary in an environment that is internet-facing but has
    # the component disabled. Neither fact is visible from the vectors alone.
    risk = weighed(ON_THE_BOUNDARY, ghsa=HIGH_LOW, redhat=HIGH_HIGH)
    assert risk.band_depends_on_the_source
    assert [one.score for one in risk.scores] == [23.5, 25.0]
    assert risk.bands == ("Medium", "Low")


def test_a_council_that_settled_a_vector_gives_one_score_and_not_a_range():
    one = finding(ghsa=TOTAL_LOSS, nvd=LOW_CONFIDENTIALITY)
    risk = assess(one, WORKED_EXAMPLE_ANSWERS, from_council(CVSS_8_0))
    assert len(risk.scores) == 1
    assert risk.scores[0].score == 44.0
    assert "council" in risk.scores[0].technical.derived_from


def test_a_finding_nobody_scored_is_still_weighed_and_comes_out_provisional():
    # Not omitted and not a zero assessment: technical contributes nothing and
    # the whole thing is flagged.
    risk = weighed()
    assert len(risk.scores) == 1
    assert isinstance(risk.scores[0].technical, UnknownTechnicalSeverity)
    assert risk.scores[0].technical_score == 0.0
    assert risk.is_provisional


def test_an_unknown_answer_flags_the_score_rather_than_reading_as_no():
    unsure = {**WORKED_EXAMPLE_ANSWERS, "THR-1": Answer.UNKNOWN}
    risk = weighed(unsure, ghsa=CVSS_8_0)
    assert risk.is_provisional
    assert risk.scores[0].unknown_questions == ("THR-1",)
    assert risk.scores[0].score == 44.0


def test_not_applicable_leaves_the_score_settled():
    aside = {**WORKED_EXAMPLE_ANSWERS, "THR-1": Answer.NOT_APPLICABLE}
    assert not weighed(aside, ghsa=CVSS_8_0).is_provisional


def test_every_source_is_weighed_against_the_same_environment():
    risk = weighed(ghsa=TOTAL_LOSS, nvd=LOW_CONFIDENTIALITY)
    first, second = risk.scores
    assert (first.exposure, first.business, first.threat) == (
        second.exposure,
        second.business,
        second.threat,
    )


def test_the_bands_a_finding_reaches_are_named_worst_first():
    assert weighed(ON_THE_BOUNDARY, a=HIGH_LOW, b=HIGH_HIGH).bands == ("Medium", "Low")


def test_a_finding_offered_no_technical_severity_at_all_is_refused():
    with pytest.raises(ValueError, match="was offered no technical severity"):
        assess(finding(ghsa=CVSS_8_0), WORKED_EXAMPLE_ANSWERS, ())


def test_the_same_answers_weigh_the_same_way_every_time():
    assert weighed(ghsa=CVSS_8_0) == weighed(ghsa=CVSS_8_0)


def test_scoring_an_incomplete_answer_set_is_refused_whoever_asks():
    # Held on the type that scores, not only where a file is read. An unanswered
    # question was scoring as a No, and no caller may reach that again -- the
    # file reader is one caller, and it is not the only one.
    short = {identifier: given for identifier, given in WORKED_EXAMPLE_ANSWERS.items()
             if identifier != "EXP-1"}
    one = finding(ghsa=CVSS_8_0)
    with pytest.raises(ValueError, match="^EXP-1 unanswered"):
        assess(one, short, per_source(one))


def test_scoring_with_no_answers_at_all_is_refused_rather_than_read_as_all_no():
    one = finding(ghsa=CVSS_8_0)
    with pytest.raises(ValueError, match="unanswered; the approved library asks all 12"):
        assess(one, {}, per_source(one))
