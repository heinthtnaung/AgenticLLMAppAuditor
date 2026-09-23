"""Guards on how far apart the sources are, and on the order that follows from it."""

import pytest

from cvss.score import SEVERITY_BANDS
from report.disagreement import (
    BAND_ORDER,
    bands_crossed,
    crosses_a_band,
    most_contested_first,
    score_spread,
    sources_disagree,
)
from report_samples import (
    BOTTOM_OF_HIGH,
    CONFIDENTIALITY_ONLY,
    HARMLESS,
    LOW_CONFIDENTIALITY,
    TOP_OF_MEDIUM,
    WIDE_WITHIN_MEDIUM,
    SAME_SCORE_ONE,
    SAME_SCORE_TWO,
    TOTAL_LOSS,
    component,
    finding,
)


def test_sources_that_read_a_metric_differently_disagree():
    assert sources_disagree(finding(vectors={"a": TOTAL_LOSS, "b": LOW_CONFIDENTIALITY}))


def test_sources_agreeing_on_the_same_number_can_still_disagree():
    # The deceptive case, and the reason disagreement asks the vectors rather
    # than the scores: both of these come to 6.5 and they are not the same
    # reading. Measured by score they would be filed as agreeing.
    contested = finding(vectors={"ghsa": SAME_SCORE_ONE, "nvd": SAME_SCORE_TWO})
    assert [score.base_score for score in contested.scores] == [6.5, 6.5]
    assert score_spread(contested) == 0.0
    assert sources_disagree(contested)
    assert contested.disputed_metrics() == ("I", "A")


def test_one_source_disagrees_with_nobody():
    assert not sources_disagree(finding(vectors={"ghsa": TOTAL_LOSS}))


def test_sources_reading_a_vector_the_same_way_agree():
    assert not sources_disagree(finding(vectors={"a": TOTAL_LOSS, "b": TOTAL_LOSS}))


@pytest.mark.parametrize(
    ("vectors", "expected"),
    [
        ({"a": TOTAL_LOSS, "b": LOW_CONFIDENTIALITY}, 4.5),
        ({"a": TOTAL_LOSS, "b": CONFIDENTIALITY_ONLY}, 2.3),
        ({"a": TOTAL_LOSS}, 0.0),
        ({}, 0.0),
    ],
    ids=["9.8 and 5.3", "9.8 and 7.5", "one source", "no source"],
)
def test_the_spread_is_the_distance_between_the_furthest_apart(vectors, expected):
    assert score_spread(finding(vectors=vectors)) == expected


def test_the_bands_are_read_off_the_cvss_bands_rather_than_restated():
    # Restating them here would let the two drift and file a finding under a
    # band the calculator does not use.
    assert BAND_ORDER == tuple(name for _, name in SEVERITY_BANDS)


def test_the_bands_a_finding_reaches_are_named_worst_first():
    spanning = finding(vectors={"a": TOTAL_LOSS, "b": LOW_CONFIDENTIALITY, "c": HARMLESS})
    assert bands_crossed(spanning) == ("Critical", "Medium", "None")


def test_sources_in_one_band_cross_nothing():
    assert not crosses_a_band(finding(vectors={"a": SAME_SCORE_ONE, "b": LOW_CONFIDENTIALITY}))


def test_sources_in_different_bands_cross_one():
    assert crosses_a_band(finding(vectors={"a": TOTAL_LOSS, "b": CONFIDENTIALITY_ONLY}))


def test_a_disagreement_that_changes_the_band_outranks_a_much_wider_one_that_does_not():
    # A spread inside one band moves a number; a spread across a boundary moves
    # the response time, which is a decision. A tenth of a point across the
    # Medium/High line comes first, ahead of 2.9 that stays inside Medium.
    crossing = finding(
        component("crossing"),
        advisory_id="CVE-1",
        vectors={"a": TOP_OF_MEDIUM, "b": BOTTOM_OF_HIGH},
    )
    wider = finding(
        component("wider"),
        advisory_id="CVE-2",
        vectors={"a": WIDE_WITHIN_MEDIUM, "b": TOP_OF_MEDIUM},
    )
    assert (score_spread(crossing), score_spread(wider)) == (0.1, 2.9)
    assert crosses_a_band(crossing) and not crosses_a_band(wider)
    ordered = most_contested_first((wider, crossing))
    assert [one.component.name for one in ordered] == ["crossing", "wider"]


def test_among_findings_crossing_the_same_bands_the_wider_spread_comes_first():
    # Once two disagreements would change the same decision, how far apart the
    # sources are is what is left to rank them by.
    wider = finding(
        component("wider"), advisory_id="CVE-2", vectors={"a": TOTAL_LOSS, "b": LOW_CONFIDENTIALITY}
    )
    narrower = finding(
        component("narrower"), advisory_id="CVE-1", vectors={"a": TOTAL_LOSS, "b": TOP_OF_MEDIUM}
    )
    assert bands_crossed(wider) == bands_crossed(narrower) == ("Critical", "Medium")
    assert (score_spread(wider), score_spread(narrower)) == (4.5, 2.9)
    ordered = most_contested_first((narrower, wider))
    assert [one.component.name for one in ordered] == ["wider", "narrower"]


def test_findings_that_tie_order_by_name_so_two_runs_agree():
    first = finding(component("a"), advisory_id="CVE-1", vectors={"x": TOTAL_LOSS, "y": HARMLESS})
    second = finding(component("b"), advisory_id="CVE-2", vectors={"x": TOTAL_LOSS, "y": HARMLESS})
    assert most_contested_first((second, first)) == most_contested_first((first, second))
    assert [one.advisory.advisory_id for one in most_contested_first((second, first))] == [
        "CVE-1",
        "CVE-2",
    ]
