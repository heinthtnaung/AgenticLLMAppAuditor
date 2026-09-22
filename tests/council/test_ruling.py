"""Guards on the ruling types: a record that says what was decided, and what was not."""

import pytest

from council.answer import Confidence
from council.ruling import (
    Basis,
    ContestedMetric,
    NoFallbackPublished,
    PublishedFallback,
    SettledMetric,
    UnresolvedMetric,
)
from council_samples import answer


def settled(**overrides) -> SettledMetric:
    """Build one settled ruling, changed where a test needs it."""
    fields = {
        "metric": "AV",
        "value": "N",
        "confidence": Confidence.HIGH,
        "basis": Basis.AGREED,
        "supporting": (answer(),),
    }
    fields.update(overrides)
    return SettledMetric(**fields)


def test_a_settled_ruling_keeps_the_answers_it_rests_on():
    ruling = settled(supporting=(answer(name="one"), answer(name="two")))
    assert [item.member.name for item in ruling.supporting] == ["one", "two"]


def test_the_basis_names_the_members_it_ranges_over():
    # Not "answered", which a reader cannot resolve now there are three reply
    # types: a guess dissenting still leaves the basis AGREED, and the string
    # has to say why rather than invite the reading that nobody dissented.
    assert Basis.AGREED.value == "every member that offered a quotation supported this value"
    assert "offering quotations disagreed" in Basis.EVIDENCE.value


def test_a_ruling_that_rests_on_no_answer_is_refused():
    with pytest.raises(ValueError, match="cannot be settled by no answer"):
        settled(supporting=())


def test_a_ruling_settled_against_its_own_answers_is_refused():
    with pytest.raises(ValueError, match="was settled on N by answers supporting L"):
        settled(supporting=(answer(value="L"),))


def test_a_ruling_on_a_value_the_metric_forbids_is_refused():
    with pytest.raises(ValueError, match="is not a value of"):
        settled(value="Z", supporting=())


def test_a_contest_needs_more_than_one_value_to_be_a_contest():
    with pytest.raises(ValueError, match="is not contested"):
        ContestedMetric("AV", (answer(name="one"), answer(name="two")))


def test_a_contest_between_two_values_is_recorded():
    contested = ContestedMetric("AV", (answer(value="N"), answer(value="L", name="two")))
    assert {candidate.value for candidate in contested.candidates} == {"N", "L"}


def test_a_fallback_must_name_the_published_source_it_came_from():
    # There is usually more than one published vector and they often differ, so
    # a fallback that does not say which is not a record.
    with pytest.raises(ValueError, match="must name the published source"):
        PublishedFallback(value="L", source="")


def test_a_fallback_with_no_value_is_refused():
    with pytest.raises(ValueError, match="carries no value"):
        PublishedFallback(value="", source="nvd")


def test_an_absent_fallback_must_say_why():
    with pytest.raises(ValueError, match="must say why nothing was published"):
        NoFallbackPublished(reason="")


def test_an_unresolved_ruling_records_which_source_its_value_came_from():
    ruling = UnresolvedMetric("AV", PublishedFallback(value="L", source="redhat"))
    assert ruling.fallback.source == "redhat"


def test_an_unresolved_ruling_whose_fallback_the_metric_forbids_is_refused():
    with pytest.raises(ValueError, match="is not a value of"):
        UnresolvedMetric("AV", PublishedFallback(value="Z", source="nvd"))


def test_an_unresolved_ruling_needs_one_of_the_two_fallback_kinds():
    with pytest.raises(TypeError, match="needs a PublishedFallback"):
        UnresolvedMetric("AV", "nvd said L")


@pytest.mark.parametrize("metric", ["ZZ", "E", ""], ids=["unknown", "temporal", "empty"])
def test_a_ruling_about_no_real_metric_is_refused(metric):
    with pytest.raises(ValueError, match="is not a CVSS Base metric"):
        UnresolvedMetric(metric, PublishedFallback(value="L", source="nvd"))


def test_a_ruling_is_frozen():
    with pytest.raises(AttributeError):
        settled().value = "L"
