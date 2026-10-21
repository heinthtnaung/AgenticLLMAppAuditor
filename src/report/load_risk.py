"""Reading a saved report's organisation risk back, by re-running the scoring engine.

The score, its bands, floors and clamp are **not read** from the record: only the
answers the organisation gave are, by question id, and the real engine
(`organisation.risk.assess`) weighs them again against the finding's own published
sources. So a figure in the file that does not follow from its answers is not
trusted -- the engine re-derives every number, and the guard in `cli.approve`
refuses a re-render that does not match the file.

A finding the record scored null carries no answers and no risk: `risk_from`
gives None, and the approval is recorded without inventing a score nobody asked.
"""

from typing import Any, Mapping

from findings.finding import Finding
from organisation.risk import FindingRisk, assess, per_source
from report.load_json import ReportJsonFault, as_list, require, required_object
from scoring.question import Answer

CATEGORIES = ("exposure", "business", "threat")
ANSWER_BY_WORD = {given.value: given for given in Answer}


def risk_from(finding: Finding, block: Mapping[str, Any], where: str) -> FindingRisk | None:
    """Rebuild one finding's risk by weighing its recorded answers, or None where it scored none."""
    risk = block.get("organisation_risk")
    if risk is None:
        return None
    answers_by_id = answers_from(required_object(risk, "categories", f"{where}.organisation_risk"))
    return assess(finding, answers_by_id, per_source(finding))


def answers_from(categories: Mapping[str, Any]) -> dict[str, Answer]:
    """Read every answer one finding was weighed from, by question id, over its categories."""
    answered: dict[str, Answer] = {}
    for name in CATEGORIES:
        answered.update(category_answers(required_object(categories, name, "categories")))
    return answered


def category_answers(category: Mapping[str, Any]) -> dict[str, Answer]:
    """Read one category's answers back as a map of question id to the answer given."""
    entries = as_list(require(category, "answers", "categories"), "categories.answers")
    return dict(answered(one) for one in entries)


def answered(block: Mapping[str, Any]) -> tuple[str, Answer]:
    """Read one answer: the question it answers and the word the environment chose."""
    question_id = str(require(block, "question_id", "categories.answers"))
    word = str(require(block, "answer", "categories.answers"))
    answer = ANSWER_BY_WORD.get(word)
    if answer is None:
        allowed = ", ".join(ANSWER_BY_WORD)
        raise ReportJsonFault(f"{question_id} is answered {word!r}; an answer is {allowed}")
    return question_id, answer
