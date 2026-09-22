"""The vocabulary of an organisation assessment: categories, answers, and questions.

Each question carries its own weight, because `Yes = +10` everywhere says that
every fact about an environment matters equally, and they do not: a service on
the public internet and a service behind a segment boundary are not two ticks of
the same size. What Yes is worth is a property of the question.

The questions themselves are not here. An approved template library is its own
component and is not built; this module is the shape a question has to be in for
the engine to weigh it.
"""

import math
from dataclasses import dataclass
from enum import Enum


class Category(Enum):
    """The four categories the Organisation Risk Score weighs, by their names in the design."""

    TECHNICAL = "Technical severity"
    EXPOSURE = "Exposure and reachability"
    BUSINESS = "Business impact"
    THREAT = "Threat and exploitation"


class Answer(Enum):
    """What an organisation can say about one question."""

    YES = "Yes"
    NO = "No"
    UNKNOWN = "Unknown"
    NOT_APPLICABLE = "N/A"


@dataclass(frozen=True)
class Question:
    """One question and what answering Yes is worth in its category."""

    question_id: str
    text: str
    category: Category
    yes_weight: float

    def __post_init__(self) -> None:
        """Refuse a question that cannot be recorded, cited, or weighed."""
        if not self.question_id or not self.text:
            raise ValueError("A question needs an id and its text, so a score can cite it")
        if not isinstance(self.category, Category):
            raise TypeError(
                f"{self.question_id!r} must carry a Category, "
                f"not {type(self.category).__name__}"
            )
        if not math.isfinite(self.yes_weight):
            raise ValueError(f"{self.question_id!r} has no usable weight: {self.yes_weight!r}")


def contribution_of(question: Question, answer: Answer) -> float:
    """Give what one answer adds to its category's raw total."""
    # Only Yes moves a number. No, Unknown and N/A all add nothing, and what
    # separates them is not arithmetic: N/A says the question does not apply
    # here, and Unknown says nobody has looked yet and makes the score
    # provisional. Scoring Unknown as anything else would invent an answer.
    if answer is Answer.YES:
        return question.yes_weight
    return 0.0


def question_order(question: Question) -> str:
    """Order questions so two runs over one assessment produce identical output."""
    return question.question_id
