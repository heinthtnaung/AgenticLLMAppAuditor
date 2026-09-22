"""One category's score: every answer weighed, summed, and then clamped to 0-100.

**The clamp is before the weighting, not after.** That ordering is the whole
reason this is a step of its own and it is invisible in the result, so it is
pinned here and by a test. A category full of compensating controls stops at 0;
an unclamped one would go negative and buy down the other three, so a segmented
network would reduce business impact. A control reduces risk in its own category
and no further.
"""

import math
from dataclasses import dataclass
from typing import Mapping

from scoring.question import Answer, Category, Question, contribution_of, question_order
from scoring.scale import MAXIMUM_CATEGORY_SCORE, MINIMUM_CATEGORY_SCORE


@dataclass(frozen=True)
class AnsweredQuestion:
    """One question, the organisation's answer, and what that answer contributed."""

    question: Question
    answer: Answer
    contribution: float


@dataclass(frozen=True)
class CategoryScore:
    """One category's score, with every answer kept beside it so the number re-derives."""

    category: Category
    answers: tuple[AnsweredQuestion, ...]
    raw_total: float
    score: float

    def __post_init__(self) -> None:
        """Refuse a record whose number does not follow from what is kept beside it."""
        # `score_category` always clamps, so nothing built through it can fail
        # these. A hand-built one could, and it would carry an unclamped category
        # straight past the weighting -- which is the one invariant this engine
        # rests on. The type holds it, not only its constructor.
        if not isinstance(self.category, Category):
            raise TypeError(
                f"A category score must carry a Category, not {type(self.category).__name__}"
            )
        refuse_unfounded_total(self.answers, self.raw_total)
        refuse_unclamped_score(self.raw_total, self.score)

    @property
    def unknown_questions(self) -> tuple[str, ...]:
        """Name the questions answered Unknown, so the provisional flag can be acted on."""
        return tuple(
            answered.question.question_id
            for answered in self.answers
            if answered.answer is Answer.UNKNOWN
        )

    @property
    def is_provisional(self) -> bool:
        """Say whether an unanswered question makes this category's score provisional."""
        return bool(self.unknown_questions)

    @property
    def was_clamped(self) -> bool:
        """Say whether the clamp moved the raw total, which the score alone cannot show."""
        return self.raw_total != self.score


def score_category(category: Category, answers: Mapping[Question, Answer]) -> CategoryScore:
    """Score one category from its answers, clamped to 0-100 before anything weights it."""
    refuse_foreign_questions(category, answers)
    refuse_repeated_ids(answers)
    answered = [
        answer_one(question, answers[question])
        for question in sorted(answers, key=question_order)
    ]
    raw_total = math.fsum(item.contribution for item in answered)
    return CategoryScore(
        category=category,
        answers=tuple(answered),
        raw_total=raw_total,
        score=clamp(raw_total),
    )


def answer_one(question: Question, answer: Answer) -> AnsweredQuestion:
    """Record one answer and what it contributed, so the total can be checked by hand."""
    if not isinstance(answer, Answer):
        raise TypeError(
            f"{question.question_id!r} must be answered Yes, No, Unknown or N/A, "
            f"not {type(answer).__name__}"
        )
    return AnsweredQuestion(
        question=question,
        answer=answer,
        contribution=contribution_of(question, answer),
    )


def clamp(raw_total: float) -> float:
    """Hold a raw category total inside 0-100, before any weighting sees it."""
    return min(max(raw_total, MINIMUM_CATEGORY_SCORE), MAXIMUM_CATEGORY_SCORE)


def refuse_unfounded_total(answers: tuple[AnsweredQuestion, ...], raw_total: float) -> None:
    """Refuse a raw total the answers kept beside it do not add up to."""
    if not math.isfinite(raw_total):
        raise ValueError(f"{raw_total!r} is no category total")
    contributed = math.fsum(answered.contribution for answered in answers)
    if contributed == raw_total:
        return
    raise ValueError(
        f"A raw total of {raw_total} does not follow from its answers, which add to {contributed}"
    )


def refuse_unclamped_score(raw_total: float, score: float) -> None:
    """Refuse a score that is not its raw total clamped, which is this engine's one invariant."""
    clamped = clamp(raw_total)
    if score == clamped:
        return
    raise ValueError(
        f"A category score is its raw total clamped to "
        f"{MINIMUM_CATEGORY_SCORE:g}-{MAXIMUM_CATEGORY_SCORE:g}: "
        f"{raw_total} clamps to {clamped}, not {score}"
    )


def refuse_repeated_ids(answers: Mapping[Question, Answer]) -> None:
    """Refuse two questions sharing an id, which have no settled order between them."""
    # Answers are ordered by id, so a repeated id leaves two records in whichever
    # order the caller happened to build them: the score would be stable and the
    # report beside it would not. It is a fault in the question library.
    identifiers = sorted(question.question_id for question in answers)
    repeated = sorted({name for name in identifiers if identifiers.count(name) > 1})
    if not repeated:
        return
    raise ValueError(f"{', '.join(repeated)} is given by more than one question")


def refuse_foreign_questions(category: Category, answers: Mapping[Question, Answer]) -> None:
    """Refuse a question belonging to another category, which would score the wrong one."""
    if not isinstance(answers, Mapping):
        raise TypeError(
            f"Answers must be a mapping of question to answer, not {type(answers).__name__}"
        )
    foreign = sorted(q.question_id for q in answers if q.category is not category)
    if not foreign:
        return
    raise ValueError(
        f"{', '.join(foreign)} do not belong to {category.value} and cannot score it"
    )
