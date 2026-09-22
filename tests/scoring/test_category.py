"""Guards on one category's score: per-question weights, and the clamp before weighting."""

import pytest

from scoring.category import AnsweredQuestion, CategoryScore, clamp, score_category
from scoring.question import Answer, Category, Question
from scoring_samples import (
    BUSINESS_CRITICAL,
    BUSINESS_QUESTIONS,
    DISABLED,
    EXPOSURE_QUESTIONS,
    INTERNET_FACING,
    IN_PRODUCTION,
    PORT_EXPOSED,
    SEGMENTED,
    all_answered,
)

NO_EXPOSURE = all_answered(EXPOSURE_QUESTIONS, Answer.NO)

# Three questions that can only be answered past the top of the scale.
OVER_THE_TOP = tuple(
    Question(f"EXP-9{n}", f"Is it exposed in way {n}?", Category.EXPOSURE, 60) for n in (1, 2, 3)
)


def test_each_question_pays_its_own_weight():
    answers = {**NO_EXPOSURE, INTERNET_FACING: Answer.YES, PORT_EXPOSED: Answer.YES}
    assert score_category(Category.EXPOSURE, answers).score == 60


def test_a_compensating_control_subtracts_in_its_own_category():
    answers = {**NO_EXPOSURE, INTERNET_FACING: Answer.YES, SEGMENTED: Answer.YES}
    assert score_category(Category.EXPOSURE, answers).score == 25


def test_strong_controls_clamp_at_zero_rather_than_going_negative():
    # Segmented and disabled are worth -45 between them with nothing positive
    # answered. Unclamped, that would buy down the other three categories.
    answers = {**NO_EXPOSURE, SEGMENTED: Answer.YES, DISABLED: Answer.YES}
    scored = score_category(Category.EXPOSURE, answers)
    assert scored.raw_total == -45
    assert scored.score == 0
    assert scored.was_clamped


def test_a_category_over_the_top_clamps_at_one_hundred():
    scored = score_category(Category.EXPOSURE, all_answered(OVER_THE_TOP, Answer.YES))
    assert scored.raw_total == 180
    assert scored.score == 100
    assert scored.was_clamped


def test_a_category_inside_the_scale_is_not_clamped():
    scored = score_category(Category.EXPOSURE, {**NO_EXPOSURE, INTERNET_FACING: Answer.YES})
    assert scored.raw_total == scored.score == 40
    assert not scored.was_clamped


@pytest.mark.parametrize(
    ("value", "expected"),
    [(-45.0, 0.0), (-0.1, 0.0), (0.0, 0.0), (100.0, 100.0), (100.1, 100.0), (180.0, 100.0)],
)
def test_the_clamp_holds_both_ends(value, expected):
    assert clamp(value) == expected


def test_an_unknown_answer_makes_the_category_provisional():
    answers = {**NO_EXPOSURE, INTERNET_FACING: Answer.UNKNOWN}
    scored = score_category(Category.EXPOSURE, answers)
    assert scored.is_provisional
    assert scored.unknown_questions == ("EXP-1",)


def test_an_unknown_answer_is_not_silently_a_no():
    # It contributes the same nothing a No does, and the flag is what stops the
    # number being read as settled. Without it the two would be indistinguishable.
    unknown = score_category(Category.EXPOSURE, {**NO_EXPOSURE, INTERNET_FACING: Answer.UNKNOWN})
    refused = score_category(Category.EXPOSURE, NO_EXPOSURE)
    assert unknown.score == refused.score == 0
    assert unknown.is_provisional
    assert not refused.is_provisional


def test_not_applicable_is_neither_a_no_nor_an_unknown():
    answers = {**NO_EXPOSURE, INTERNET_FACING: Answer.NOT_APPLICABLE}
    scored = score_category(Category.EXPOSURE, answers)
    assert scored.score == 0
    assert not scored.is_provisional
    assert scored.unknown_questions == ()
    recorded = {item.question.question_id: item.answer for item in scored.answers}
    assert recorded["EXP-1"] is Answer.NOT_APPLICABLE


def test_every_unknown_question_is_named_in_question_order():
    answers = {**NO_EXPOSURE, PORT_EXPOSED: Answer.UNKNOWN, INTERNET_FACING: Answer.UNKNOWN}
    assert score_category(Category.EXPOSURE, answers).unknown_questions == ("EXP-1", "EXP-3")


def test_every_answer_is_kept_so_the_total_re_derives():
    answers = {**NO_EXPOSURE, INTERNET_FACING: Answer.YES, SEGMENTED: Answer.YES}
    scored = score_category(Category.EXPOSURE, answers)
    asked = [item.question.question_id for item in scored.answers]
    assert asked == ["EXP-1", "EXP-2", "EXP-3", "EXP-4", "EXP-5"]
    assert sum(item.contribution for item in scored.answers) == scored.raw_total


def test_the_business_questions_of_the_worked_example_come_to_eighty():
    scored = score_category(Category.BUSINESS, all_answered(BUSINESS_QUESTIONS, Answer.YES))
    assert scored.score == 80
    assert {item.question for item in scored.answers} == set(BUSINESS_QUESTIONS)


def test_a_category_with_no_questions_scores_nothing_and_is_settled():
    scored = score_category(Category.THREAT, {})
    assert scored.score == 0
    assert scored.answers == ()
    assert not scored.is_provisional


def test_the_same_answers_always_give_the_same_category_score():
    first = score_category(Category.EXPOSURE, {INTERNET_FACING: Answer.YES, SEGMENTED: Answer.NO})
    second = score_category(Category.EXPOSURE, {SEGMENTED: Answer.NO, INTERNET_FACING: Answer.YES})
    assert first == second


def test_a_question_from_another_category_is_refused():
    with pytest.raises(ValueError, match="BUS-1 do not belong to Exposure and reachability"):
        score_category(Category.EXPOSURE, {BUSINESS_CRITICAL: Answer.YES})


def test_several_foreign_questions_are_all_named():
    answers = {BUSINESS_CRITICAL: Answer.YES, IN_PRODUCTION: Answer.NO}
    with pytest.raises(ValueError, match="BUS-1, BUS-2"):
        score_category(Category.EXPOSURE, answers)


@pytest.mark.parametrize("given", ["Yes", True, 1, None], ids=["str", "bool", "int", "none"])
def test_something_that_is_no_answer_is_refused(given):
    with pytest.raises(TypeError, match="must be answered Yes, No, Unknown or N/A"):
        score_category(Category.EXPOSURE, {INTERNET_FACING: given})


@pytest.mark.parametrize("given", [None, [], "EXP-1"], ids=["none", "list", "str"])
def test_answers_that_are_no_mapping_are_refused(given):
    with pytest.raises(TypeError, match="must be a mapping of question to answer"):
        score_category(Category.EXPOSURE, given)


def test_a_category_score_is_frozen():
    scored = score_category(Category.EXPOSURE, NO_EXPOSURE)
    with pytest.raises(AttributeError):
        scored.score = 100


def answered_worth(contribution: float) -> tuple[AnsweredQuestion, ...]:
    """One answered question contributing exactly what a test needs."""
    question = Question("EXP-X", "Is it?", Category.EXPOSURE, contribution)
    return (AnsweredQuestion(question, Answer.YES, contribution),)


@pytest.mark.parametrize(
    ("raw_total", "score"),
    [(400.0, 400.0), (-400.0, -400.0), (40.0, 50.0)],
    ids=["above the top", "below the bottom", "unrelated to the total"],
)
def test_a_category_score_that_is_not_its_total_clamped_is_refused(raw_total, score):
    # A hand-built 400 would reach the weighting unclamped and come out Critical;
    # the slot guard in the engine checks the category, not the arithmetic. The
    # clamp is what this engine rests on, so the type holds it and not only
    # `score_category`, which is the sole constructor that gets it right.
    with pytest.raises(ValueError, match="is its raw total clamped"):
        CategoryScore(Category.EXPOSURE, answered_worth(raw_total), raw_total, score)


def test_a_total_its_own_answers_do_not_add_up_to_is_refused():
    with pytest.raises(ValueError, match="does not follow from its answers"):
        CategoryScore(Category.EXPOSURE, answered_worth(40.0), 400.0, 100.0)


def test_a_category_score_carrying_no_category_is_refused():
    with pytest.raises(TypeError, match="must carry a Category"):
        CategoryScore("Exposure", answered_worth(40.0), 40.0, 40.0)


def test_a_well_formed_hand_built_score_is_accepted():
    built = CategoryScore(Category.EXPOSURE, answered_worth(400.0), 400.0, 100.0)
    assert built.score == 100.0
    assert built.was_clamped


def test_two_questions_sharing_an_id_are_refused():
    # Answers are ordered by id, so a repeat has no settled order between its two
    # records: the score would be stable and the record beside it would not.
    twin = Question("EXP-1", "Is it something else entirely?", Category.EXPOSURE, 5)
    with pytest.raises(ValueError, match="EXP-1 is given by more than one question"):
        score_category(Category.EXPOSURE, {INTERNET_FACING: Answer.YES, twin: Answer.YES})
