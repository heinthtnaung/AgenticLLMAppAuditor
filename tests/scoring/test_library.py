"""Guards on the approved library: the design's own weights, and nobody else's."""

import pytest

from scoring.library import (
    QUESTIONS_BY_ID,
    APPROVED_QUESTIONS,
    BUSINESS_QUESTIONS,
    EXPOSURE_QUESTIONS,
    answers_for,
    question,
    questions_of,
)
from scoring.category import score_category
from scoring.question import Answer, Category, Question

# docs/SCORING_MODEL.md, "Turning answers into a category score", quoted.
DESIGNS_EXPOSURE_TABLE = {
    "Is the affected service internet-facing?": 40,
    "Is it reachable from an untrusted network?": 25,
    "Is the vulnerable port or API exposed?": 20,
    "Is the asset isolated or segmented?": -15,
    "Is the component disabled?": -30,
}


def test_the_exposure_table_is_the_designs_own_weight_for_weight():
    # The one table the design fixes. A weight that drifts from it is a silent
    # disagreement with the document this project works to.
    assert {asked.text: asked.yes_weight for asked in EXPOSURE_QUESTIONS} == DESIGNS_EXPOSURE_TABLE


def test_a_compensating_control_subtracts_rather_than_adding_nothing():
    assert question("EXP-4").yes_weight < 0
    assert question("EXP-5").yes_weight < 0


def test_the_worked_examples_business_answers_come_to_eighty():
    # The design pins business impact only through its worked example:
    # business-critical, production and sensitive data together make 80.
    given = {"BUS-1": Answer.YES, "BUS-2": Answer.YES, "BUS-3": Answer.YES}
    assert score_category(Category.BUSINESS, answers_for(Category.BUSINESS, given)).score == 80


def test_no_question_asks_about_technical_severity():
    # It comes from the published vectors, not from asking anybody.
    assert all(asked.category is not Category.TECHNICAL for asked in APPROVED_QUESTIONS)


def test_technical_severity_cannot_even_be_asked_for():
    with pytest.raises(ValueError, match="is not asked of an organisation"):
        questions_of(Category.TECHNICAL)


def test_every_question_carries_its_own_weight_rather_than_a_flat_ten():
    weights = {asked.yes_weight for asked in APPROVED_QUESTIONS}
    assert len(weights) > 1
    assert 10 not in weights or len(weights) > 2


def test_every_approved_question_has_an_id_nobody_else_uses():
    identifiers = [asked.question_id for asked in APPROVED_QUESTIONS]
    assert len(set(identifiers)) == len(identifiers)


def test_a_question_nobody_approved_cannot_be_answered():
    # The gate. A caller answers by id and never holds a Question, so a caller
    # can never introduce one or weigh an approved one differently.
    with pytest.raises(ValueError, match="not a question in the approved library"):
        answers_for(Category.EXPOSURE, {"EXP-99": Answer.YES})


def test_a_caller_cannot_slip_its_own_question_in_by_handing_over_the_object():
    # The bypass the gate exists to close: an id has no weight on it, so a
    # caller holding a Question is the only way a weight could be introduced,
    # and answering is by id precisely so that a caller never holds one.
    smuggled = Question("EXP-1", "Is the affected service internet-facing?", Category.EXPOSURE, 999)
    with pytest.raises(ValueError, match="not a question in the approved library"):
        answers_for(Category.EXPOSURE, {smuggled: Answer.YES})


def test_an_answer_is_resolved_to_the_librarys_question_and_its_weight():
    resolved = answers_for(Category.EXPOSURE, {"EXP-1": Answer.YES})
    asked, given = next(iter(resolved.items()))
    assert asked is question("EXP-1")
    assert (asked.yes_weight, given) == (40, Answer.YES)


def test_answers_for_one_category_leave_the_other_categories_alone():
    given = {"EXP-1": Answer.YES, "BUS-1": Answer.YES, "THR-1": Answer.YES}
    assert list(answers_for(Category.EXPOSURE, given)) == [question("EXP-1")]


def test_a_category_gives_its_questions_in_the_order_the_library_lists_them():
    assert questions_of(Category.BUSINESS) == BUSINESS_QUESTIONS


def test_every_question_belongs_to_a_category_an_organisation_is_asked_about():
    for asked in APPROVED_QUESTIONS:
        assert questions_of(asked.category)


def test_the_library_cannot_be_rewritten_by_a_caller():
    # This file claims approval is structural rather than a promise, and one
    # assignment into a plain dict would falsify that claim from outside the
    # library it is a claim about.
    with pytest.raises(TypeError):
        QUESTIONS_BY_ID["EXP-99"] = question("EXP-1")


def test_an_approved_question_cannot_be_swapped_for_another():
    with pytest.raises(TypeError):
        QUESTIONS_BY_ID["EXP-1"] = question("EXP-2")
