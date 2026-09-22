"""Guards on the Base metric table: its order, its names, its legal values.

The specification is written out again below rather than imported from the module
under test. A test that read the vocabulary out of `metrics.py` would only prove
the file equals itself, and everything downstream -- the parser, the equations,
`CvssVector.__str__` -- trusts this table in silence. So this module is a
specification guard: it fails the day the table drifts from CVSS v3.1, not the day
coverage drops.
"""

import dataclasses

import pytest

from cvss.metrics import (
    ATTACK_COMPLEXITY,
    ATTACK_VECTOR,
    AVAILABILITY,
    BASE_METRICS,
    CONFIDENTIALITY,
    IMPACT_METRICS,
    INTEGRITY,
    METRIC_ORDER,
    METRICS_BY_ABBREVIATION,
    PRIVILEGES_REQUIRED,
    SCOPE,
    SCOPE_CHANGED,
    SCOPE_UNCHANGED,
    USER_INTERACTION,
    metric_name,
)

# CVSS v3.1 specification, section 2 (Tables 1-8): every Base metric, its name in
# words, and the values it allows, each list in the order the specification prints
# it. Value order is not cosmetic -- a refusal quotes it back as "allowed values
# are N, A, L, P".
SPECIFICATION = (
    ("AV", "Attack Vector", ("N", "A", "L", "P")),
    ("AC", "Attack Complexity", ("L", "H")),
    ("PR", "Privileges Required", ("N", "L", "H")),
    ("UI", "User Interaction", ("N", "R")),
    ("S", "Scope", ("U", "C")),
    ("C", "Confidentiality", ("H", "L", "N")),
    ("I", "Integrity", ("H", "L", "N")),
    ("A", "Availability", ("H", "L", "N")),
)

# Stated outright, not derived from SPECIFICATION: the order is the thing on trial.
SPECIFICATION_ORDER = ("AV", "AC", "PR", "UI", "S", "C", "I", "A")

BASE_METRIC_COUNT = 8

NAME_CASES = [pytest.param(row[0], row[1], id=row[0]) for row in SPECIFICATION]
VALUE_CASES = [pytest.param(row[0], row[2], id=row[0]) for row in SPECIFICATION]


def test_the_table_holds_exactly_the_eight_base_metrics():
    assert len(BASE_METRICS) == BASE_METRIC_COUNT
    assert len(SPECIFICATION) == BASE_METRIC_COUNT


def test_the_metrics_stand_in_specification_order():
    # `CvssVector.__str__` rebuilds a vector by walking this order, so reordering
    # the table changes the canonical spelling of every vector in the system.
    assert tuple(metric.abbreviation for metric in BASE_METRICS) == SPECIFICATION_ORDER


def test_metric_order_is_the_table_read_top_to_bottom():
    assert METRIC_ORDER == tuple(metric.abbreviation for metric in BASE_METRICS)
    assert METRIC_ORDER == SPECIFICATION_ORDER


def test_the_abbreviation_constants_spell_the_specification_abbreviations():
    named = (
        ATTACK_VECTOR,
        ATTACK_COMPLEXITY,
        PRIVILEGES_REQUIRED,
        USER_INTERACTION,
        SCOPE,
        CONFIDENTIALITY,
        INTEGRITY,
        AVAILABILITY,
    )
    assert named == SPECIFICATION_ORDER


@pytest.mark.parametrize(("abbreviation", "name"), NAME_CASES)
def test_each_metric_carries_its_specification_name(abbreviation, name):
    assert METRICS_BY_ABBREVIATION[abbreviation].name == name


@pytest.mark.parametrize(("abbreviation", "values"), VALUE_CASES)
def test_each_metric_allows_exactly_the_specification_values(abbreviation, values):
    # Equality, not containment: an extra value would be accepted by the parser and
    # then reach the equations, which have no weight for it.
    assert METRICS_BY_ABBREVIATION[abbreviation].values == values


def test_no_abbreviation_is_used_twice():
    # A duplicate would be silently swallowed by the lookup, losing a whole metric.
    assert len(set(METRIC_ORDER)) == BASE_METRIC_COUNT


def test_no_name_is_used_twice():
    assert len({metric.name for metric in BASE_METRICS}) == BASE_METRIC_COUNT


def test_the_lookup_holds_every_metric_and_nothing_invented():
    assert set(METRICS_BY_ABBREVIATION) == set(SPECIFICATION_ORDER)


def test_the_lookup_maps_each_abbreviation_to_its_own_metric():
    mismatched = [
        abbreviation
        for abbreviation, metric in METRICS_BY_ABBREVIATION.items()
        if metric.abbreviation != abbreviation
    ]
    assert mismatched == []


def test_the_impact_metrics_are_confidentiality_integrity_availability():
    assert IMPACT_METRICS == ("C", "I", "A")


def test_the_impact_metrics_are_base_metrics_in_specification_order():
    assert tuple(name for name in METRIC_ORDER if name in IMPACT_METRICS) == IMPACT_METRICS


def test_scope_allows_unchanged_and_changed_and_nothing_else():
    # SCOPE_CHANGED and CONFIDENTIALITY are both the letter "C" by specification.
    # They are a value and a metric abbreviation, and never interchangeable.
    assert (SCOPE_UNCHANGED, SCOPE_CHANGED) == ("U", "C")
    assert METRICS_BY_ABBREVIATION[SCOPE].values == (SCOPE_UNCHANGED, SCOPE_CHANGED)


@pytest.mark.parametrize(("abbreviation", "name"), NAME_CASES)
def test_metric_name_gives_the_name_in_words(abbreviation, name):
    assert metric_name(abbreviation) == name


def test_metric_name_on_an_unknown_abbreviation_is_refused_in_words():
    # A ValueError like every other refusal in this family, and a sentence rather
    # than KeyError('XX') from the function whose job is to read as English.
    with pytest.raises(ValueError, match="'XX' is not a CVSS Base metric") as refusal:
        metric_name("XX")
    assert "AV, AC, PR, UI, S, C, I, A" in str(refusal.value)


def test_metric_name_on_a_lowercase_abbreviation_is_refused():
    # The specification abbreviations are upper case; "av" is not a spelling of AV.
    with pytest.raises(ValueError, match="'av' is not a CVSS Base metric"):
        metric_name("av")


def test_a_metric_cannot_be_edited_at_runtime():
    # The table is module state shared by every importer; one writable entry would
    # let any caller rewrite the vocabulary for the whole process.
    with pytest.raises(dataclasses.FrozenInstanceError):
        BASE_METRICS[0].name = "Something Else"


def test_the_table_itself_cannot_be_edited_at_runtime():
    with pytest.raises(TypeError):
        BASE_METRICS[0] = None
