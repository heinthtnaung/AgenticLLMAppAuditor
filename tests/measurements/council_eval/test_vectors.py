"""Guards on the vector measures: the engine's score, R1's departures, and the published range."""

import eval_samples as samples
from council_eval.reference import NO_FULL_REFERENCE
from council_eval.vectors import reference_band, vector_measures
from report.council_record import CouncilAssessment, CouncilWithoutVector

LOCAL = "CVSS:3.1/AV:L/AC:H/PR:H/UI:R/S:C/C:H/I:H/A:H"


def reached(vector: str = LOCAL) -> CouncilAssessment:
    """Build a council record that handed over one vector."""
    return CouncilAssessment(advisory_id=samples.KEY, vector=vector, single_assessor=False)


def test_only_the_vectors_reached_are_measured():
    stopped = CouncilWithoutVector(advisory_id="CVE-2", single_assessor=False)
    assert len(vector_measures((samples.item(),), (reached(), stopped))) == 1


def test_the_score_and_band_are_the_engine_s():
    (measure,) = vector_measures((samples.item(),), (reached(),))
    assert (measure.score, measure.band) == (7.2, "High")


def test_the_departures_from_r1_are_named_in_specification_order():
    (measure,) = vector_measures((samples.item(),), (reached(),))
    assert measure.departs_on == ("AV", "AC", "PR", "UI", "S", "C", "I")
    assert measure.referenced == 8


def test_a_score_between_the_published_ones_is_inside_their_range():
    # The sample's sources publish 7.5, 5.3 and 7.5.
    inside = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:L"
    (measure,) = vector_measures((samples.item(),), (reached(inside),))
    assert measure.score == 6.5
    assert measure.inside_published_range


def test_a_score_above_every_published_one_is_outside_their_range():
    above = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
    (measure,) = vector_measures((samples.item(),), (reached(above),))
    assert not measure.inside_published_range


def test_the_reference_band_is_r1_s_where_it_has_every_metric():
    (measure,) = vector_measures((samples.item(),), (reached(),))
    assert reference_band(measure) == "High"


def test_there_is_no_reference_band_where_r1_lacks_a_metric():
    only_red_hat = {"redhat": samples.VECTORS["redhat"]}
    (measure,) = vector_measures((samples.item(vectors=only_red_hat),), (reached(),))
    assert reference_band(measure) == NO_FULL_REFERENCE
