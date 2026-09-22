"""Guards on the metric definitions: every metric covered, every value explained."""

from dataclasses import FrozenInstanceError

import pytest

from council.definitions import DEFINITIONS, MetricDefinition, definition_of
from cvss.metrics import BASE_METRICS, METRIC_ORDER

# All eight definitions together, against the roughly 2,700 tokens
# `docs/COUNCIL.md` measured them at. Four characters to the token is the usual
# rough conversion, and that measurement is what the decision to carry them in
# the prompt rather than retrieve them rests on.
DEFINITION_BUDGET_CHARACTERS = 14_000


def written_characters(definition: MetricDefinition) -> int:
    """Count what one definition costs a prompt."""
    return len(definition.measures) + sum(map(len, definition.value_meanings.values()))


def test_every_base_metric_has_a_definition():
    assert set(DEFINITIONS) == set(METRIC_ORDER)


@pytest.mark.parametrize("metric", BASE_METRICS, ids=lambda metric: metric.abbreviation)
def test_a_definition_explains_exactly_the_values_the_metric_allows(metric):
    # The two tables are held to each other here. A value `cvss.metrics` allows
    # and nobody explained would be offered to a member with no meaning attached;
    # a value explained here and not allowed there would be offered and then
    # refused by the parser when a model took the offer.
    explained = definition_of(metric.abbreviation).value_meanings
    assert tuple(explained) == metric.values


@pytest.mark.parametrize("metric", METRIC_ORDER)
def test_a_definition_says_what_its_metric_measures(metric):
    assert definition_of(metric).measures.strip()


@pytest.mark.parametrize("metric", METRIC_ORDER)
def test_every_value_meaning_opens_with_the_value_in_words(metric):
    # "N = Network. ..." and not "N = ...": a member reading a bare sentence has
    # to infer which of the values it belongs to.
    meanings = definition_of(metric).value_meanings.values()
    assert all(meaning[0].isupper() and "." in meaning for meaning in meanings)


def test_an_abbreviation_that_is_no_metric_is_refused_by_the_vocabulary():
    # Not "no definition is written": for a metric that does not exist, that
    # message would tell a reader something is missing here when what is wrong
    # is the abbreviation. `cvss.metrics` owns that refusal and makes it first.
    with pytest.raises(ValueError, match="is not a CVSS Base metric"):
        definition_of("XX")


def test_a_metric_this_table_has_lost_is_refused_rather_than_read_as_nothing(monkeypatch):
    # The state the guard is for. `test_every_base_metric_has_a_definition`
    # stops it arising from an edit, and this says what happens if it ever does:
    # a refusal naming the metric, not an AttributeError on None further down.
    monkeypatch.delitem(DEFINITIONS, "AV")
    with pytest.raises(ValueError, match="No council definition is written for 'AV'"):
        definition_of("AV")


def test_the_definitions_are_small_enough_to_be_a_constant_rather_than_a_lookup():
    assert sum(map(written_characters, DEFINITIONS.values())) < DEFINITION_BUDGET_CHARACTERS


def test_a_definition_cannot_be_edited_so_two_members_read_the_same_words():
    with pytest.raises(FrozenInstanceError):
        definition_of("AV").measures = "something else"
