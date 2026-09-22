"""Guards on the assessment vocabulary: what a question is, and what an answer is worth."""

import pytest

from scoring.question import Answer, Category, Question, contribution_of, question_order
from scoring_samples import DISABLED, INTERNET_FACING, SEGMENTED


def test_the_four_categories_are_the_ones_the_design_names():
    assert [category.value for category in Category] == [
        "Technical severity",
        "Exposure and reachability",
        "Business impact",
        "Threat and exploitation",
    ]


def test_the_four_answers_are_the_ones_the_design_allows():
    assert [answer.value for answer in Answer] == ["Yes", "No", "Unknown", "N/A"]


def test_yes_is_worth_what_its_own_question_says():
    # Never a flat +10: the design's exposure table pays 40 for the internet and
    # 20 for an exposed port, because they are not the same fact.
    assert contribution_of(INTERNET_FACING, Answer.YES) == 40
    assert contribution_of(SEGMENTED, Answer.YES) == -15
    assert contribution_of(DISABLED, Answer.YES) == -30


@pytest.mark.parametrize(
    "answer", [Answer.NO, Answer.UNKNOWN, Answer.NOT_APPLICABLE], ids=["no", "unknown", "n/a"]
)
def test_only_yes_moves_a_number(answer):
    assert contribution_of(INTERNET_FACING, answer) == 0.0


def test_unknown_and_not_applicable_are_not_the_same_answer():
    # They contribute the same nothing; what separates them is what the record
    # says and whether the score comes out provisional.
    assert Answer.UNKNOWN is not Answer.NOT_APPLICABLE
    assert Answer.UNKNOWN is not Answer.NO


@pytest.mark.parametrize(
    ("question_id", "text"), [("", "Is it?"), ("EXP-9", "")], ids=["no id", "no text"]
)
def test_a_question_that_cannot_be_cited_is_refused(question_id, text):
    with pytest.raises(ValueError, match="needs an id and its text"):
        Question(question_id, text, Category.EXPOSURE, 10)


def test_a_question_carrying_no_category_is_refused():
    with pytest.raises(TypeError, match="must carry a Category"):
        Question("EXP-9", "Is it?", "Exposure and reachability", 10)


@pytest.mark.parametrize("weight", [float("nan"), float("inf")], ids=["nan", "infinity"])
def test_a_question_with_no_usable_weight_is_refused(weight):
    with pytest.raises(ValueError, match="no usable weight"):
        Question("EXP-9", "Is it?", Category.EXPOSURE, weight)


def test_questions_order_by_their_id():
    assert question_order(INTERNET_FACING) == "EXP-1"
    assert sorted([SEGMENTED, INTERNET_FACING], key=question_order)[0] is INTERNET_FACING
