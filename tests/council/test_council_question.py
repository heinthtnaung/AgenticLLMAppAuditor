"""Guards on what every question to a local model names: its subject, for the refusals to say."""

from council.explanation_prompt import build_explanation_prompt
from council.prompt import build_prompt
from council_samples import RAW_ADVISORY


def test_a_member_s_question_is_about_its_metric_and_the_explainer_s_about_an_explanation():
    explanation = build_explanation_prompt(RAW_ADVISORY, {"AV": {"nvd": "N", "ghsa": "L"}})
    assert (build_prompt("AC", RAW_ADVISORY).subject, explanation.subject) == ("AC", "explanation")
