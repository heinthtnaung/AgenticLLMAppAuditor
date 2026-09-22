"""Guards on the contract: what a member may return, and what cannot be constructed."""

import pytest

from council.answer import (
    Confidence,
    MemberAnswer,
    MemberFoundNoEvidence,
    MemberGuessed,
    weakest_confidence,
)
from council_samples import NETWORK_QUOTATION, answer, found_nothing, guessed, identity


def test_an_answer_carries_the_five_things_the_design_names():
    given = answer()
    assert (given.metric, given.value) == ("AV", "N")
    assert given.evidence == NETWORK_QUOTATION
    assert given.confidence is Confidence.HIGH
    assert given.member.name == "small-local"


def test_the_three_confidences_are_the_ones_the_design_allows():
    assert [level.value for level in Confidence] == ["low", "medium", "high"]


@pytest.mark.parametrize("metric", ["ZZ", "E", "av", ""], ids=["unknown", "temporal", "lower", ""])
def test_an_answer_naming_no_real_metric_cannot_be_constructed(metric):
    with pytest.raises(ValueError, match="Unknown metric"):
        answer(metric=metric)


@pytest.mark.parametrize(
    ("metric", "value"), [("AV", "Z"), ("S", "X"), ("AC", "N")],
    ids=["illegal", "illegal scope", "legal for another metric"],
)
def test_an_answer_whose_value_that_metric_forbids_cannot_be_constructed(metric, value):
    # The vocabulary is `cvss.metrics`, so the council cannot drift from the
    # parser and the equations about what a metric allows.
    with pytest.raises(ValueError, match="is not a value of"):
        answer(metric=metric, value=value)


@pytest.mark.parametrize("evidence", ["", "   ", "\n"], ids=["empty", "spaces", "newline"])
def test_an_answer_with_no_quotation_at_all_cannot_be_constructed(evidence):
    with pytest.raises(ValueError, match="no quotation at all"):
        answer(evidence=evidence)


def test_an_answer_needs_a_real_confidence():
    with pytest.raises(TypeError, match="needs a Confidence"):
        MemberAnswer("AV", "N", NETWORK_QUOTATION, "high", identity())


def test_an_answer_must_name_the_member_that_gave_it():
    with pytest.raises(TypeError, match="must name the member"):
        MemberAnswer("AV", "N", NETWORK_QUOTATION, Confidence.HIGH, "small-local")


def test_finding_nothing_is_its_own_type_and_carries_no_value():
    absence = found_nothing("S")
    assert absence.metric == "S"
    assert not isinstance(absence, MemberAnswer)
    assert not hasattr(absence, "value")
    assert not hasattr(absence, "evidence")


def test_finding_nothing_about_no_real_metric_is_refused():
    with pytest.raises(ValueError, match="is not a CVSS Base metric"):
        MemberFoundNoEvidence(metric="ZZ", member=identity())


def test_finding_nothing_must_still_name_the_member():
    with pytest.raises(TypeError, match="must name the member"):
        MemberFoundNoEvidence(metric="S", member="small-local")


@pytest.mark.parametrize(
    "field", ["name", "provider", "model", "family", "prompt_version"]
)
def test_an_identity_a_reader_could_not_reconstruct_is_refused(field):
    # `docs/COUNCIL.md`: a roster nobody can reconstruct is not a council, and
    # `SCORING_MODEL.md` keeps the prompt version for audit.
    with pytest.raises(ValueError, match=f"needs {field}"):
        identity(**{field: ""})


def test_an_identity_must_say_whether_the_text_left_the_machine():
    with pytest.raises(TypeError, match="must say whether it ran local"):
        identity(ran_local="yes")


def test_an_identity_records_where_a_hosted_member_ran():
    hosted = identity("hosted", provider="openrouter", family="claude", ran_local=False)
    assert not hosted.ran_local
    assert hosted.provider == "openrouter"


@pytest.mark.parametrize(
    ("levels", "expected"),
    [
        ((Confidence.HIGH, Confidence.LOW), Confidence.LOW),
        ((Confidence.HIGH, Confidence.MEDIUM), Confidence.MEDIUM),
        ((Confidence.HIGH, Confidence.HIGH), Confidence.HIGH),
        ((Confidence.MEDIUM, Confidence.LOW, Confidence.HIGH), Confidence.LOW),
        ((Confidence.MEDIUM,), Confidence.MEDIUM),
    ],
)
def test_agreement_is_worth_what_its_weakest_member_is_worth(levels, expected):
    answers = [answer(confidence=level, name=f"member-{n}") for n, level in enumerate(levels)]
    assert weakest_confidence(answers) is expected


def test_the_weakest_of_no_answers_is_refused_rather_than_guessed():
    with pytest.raises(ValueError, match="No answers to take a confidence from"):
        weakest_confidence([])


def test_an_answer_is_frozen():
    with pytest.raises(AttributeError):
        answer().value = "L"


def test_a_guess_keeps_the_value_the_member_leaned_to():
    # Worth nothing, and still recorded: which way a member leans with nothing to
    # go on is a fact about that member, countable across a corpus.
    guess = guessed(metric="A", value="N")
    assert (guess.metric, guess.value) == ("A", "N")
    assert guess.member.name == "small-local"


def test_a_guess_is_neither_an_answer_nor_an_absence():
    guess = guessed()
    assert not isinstance(guess, MemberAnswer)
    assert not isinstance(guess, MemberFoundNoEvidence)
    assert not hasattr(guess, "evidence")
    assert not hasattr(guess, "confidence")


def test_declining_and_guessing_are_different_records():
    # An absence is a fact about the advisory; a guess is a fact about the member.
    assert type(found_nothing("A")) is not type(guessed(metric="A"))


def test_a_guess_at_a_value_the_metric_forbids_is_refused():
    with pytest.raises(ValueError, match="is not a value of"):
        guessed(metric="AV", value="Z")


def test_a_guess_must_name_the_member_that_made_it():
    with pytest.raises(TypeError, match="must name the member"):
        MemberGuessed(metric="AV", value="N", member="small-local")
