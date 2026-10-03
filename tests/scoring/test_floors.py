"""Guards on the severity floors: which answers raise a band, how far, and what never does."""

import pytest

from scoring.floors import (
    SEVERITY_FLOORS,
    AppliedFloor,
    SeverityFloor,
    applied_floors,
    floored_band,
)
from scoring.question import Answer

EXPLOITED_HIGH = "FLOOR-EXPLOITED-HIGH"
EXPOSED_CRITICAL = "FLOOR-EXPLOITED-EXPOSED-CRITICAL"
EXPLOITED = {"THR-1": Answer.YES}
EXPLOITED_EXPOSED_CRITICAL = {"THR-1": Answer.YES, "EXP-1": Answer.YES, "BUS-1": Answer.YES}


def raised_to_high(before: str) -> AppliedFloor:
    """The record rule 1 leaves when it raises a band."""
    return AppliedFloor(EXPLOITED_HIGH, ("THR-1",), before, "High")


def raised_to_critical(before: str) -> AppliedFloor:
    """The record rule 2 leaves when it raises a band."""
    return AppliedFloor(EXPOSED_CRITICAL, ("THR-1", "EXP-1", "BUS-1"), before, "Critical")


def test_the_two_rules_are_the_ones_the_operator_chose_each_with_its_reason():
    named = [(rule.rule_id, rule.answered_yes, rule.floor_band) for rule in SEVERITY_FLOORS]
    assert named == [
        (EXPLOITED_HIGH, ("THR-1",), "High"),
        (EXPOSED_CRITICAL, ("THR-1", "EXP-1", "BUS-1"), "Critical"),
    ]
    assert all(rule.reason for rule in SEVERITY_FLOORS)


@pytest.mark.parametrize("before", ["Low", "Medium"])
def test_exploited_in_the_wild_raises_a_band_to_high(before):
    assert applied_floors(before, EXPLOITED) == (raised_to_high(before),)


def test_exploited_exposed_and_critical_raises_a_band_to_critical_and_records_each_step():
    assert applied_floors("Medium", EXPLOITED_EXPOSED_CRITICAL) == (
        raised_to_high("Medium"), raised_to_critical("High"),
    )


def test_a_band_already_at_the_first_floor_records_only_the_second():
    assert applied_floors("High", EXPLOITED_EXPOSED_CRITICAL) == (raised_to_critical("High"),)


@pytest.mark.parametrize("answers", [EXPLOITED, EXPLOITED_EXPOSED_CRITICAL])
def test_a_floor_never_lowers_a_band_and_records_nothing_it_did_not_raise(answers):
    assert applied_floors("Critical", answers) == ()


@pytest.mark.parametrize("answer", [Answer.NO, Answer.UNKNOWN, Answer.NOT_APPLICABLE])
def test_only_an_explicit_yes_triggers_a_floor(answer):
    # Unknown already flags the score provisional; raising the band on it too
    # would read a guess as a fact.
    assert applied_floors("Low", {**EXPLOITED_EXPOSED_CRITICAL, "THR-1": answer}) == ()


def test_an_unanswered_question_triggers_no_floor_either():
    assert applied_floors("Low", {}) == ()


@pytest.mark.parametrize("unsure", ["EXP-1", "BUS-1"])
def test_the_critical_floor_needs_every_one_of_its_three_answers_yes(unsure):
    answers = {**EXPLOITED_EXPOSED_CRITICAL, unsure: Answer.UNKNOWN}
    assert applied_floors("Medium", answers) == (raised_to_high("Medium"),)


def test_the_band_after_the_floors_is_the_last_one_raised_to_or_the_band_itself():
    raised = applied_floors("Medium", EXPLOITED_EXPOSED_CRITICAL)
    assert floored_band("Medium", raised) == "Critical"
    assert floored_band("Medium", ()) == "Medium"


@pytest.mark.parametrize("fields, fault", [
    (("FLOOR-X", ("THR-9",), "High", "why"), "not a question in the approved library"),
    (("FLOOR-X", ("THR-1",), "Severe", "why"), "'Severe' is no organisation band"),
    (("FLOOR-X", ("THR-1",), "High", ""), "needs an id, the answers it reads, and its reason"),
])
def test_a_rule_naming_what_does_not_exist_is_refused(fields, fault):
    with pytest.raises(ValueError, match=fault):
        SeverityFloor(*fields)


@pytest.mark.parametrize("fields", [
    ("", ("THR-1",), "High", "why"),
    ("FLOOR-X", (), "High", "why"),
], ids=["no rule id", "no answers to read"])
def test_a_rule_missing_its_id_or_the_answers_it_reads_is_refused(fields):
    """A floor needs an id and the answers it reads, not only a reason the other test pins."""
    # An empty answers tuple is the dangerous one: `meets` reads it with all(),
    # and all() over nothing is True, so such a floor would fire on every score.
    with pytest.raises(ValueError, match="needs an id, the answers it reads, and its reason"):
        SeverityFloor(*fields)
