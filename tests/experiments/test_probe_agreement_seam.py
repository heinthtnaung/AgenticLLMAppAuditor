"""Does a refutation the probe really reached still read as one by the time the study sorts it?

`agreement.reason_without_a_model` recognises the probe's static refutation by
its detail text and nothing else -- a concluded probe carries no reason, so the
sentence is the only marker. Every other test of that rule feeds it a state
written by hand in `arm_fixtures`, which means the two modules could drift apart
and only the fixture would keep agreeing with itself.

So this file joins them with no hand-written state anywhere in between: an app
is written into `tmp_path`, `compare_models._arm` audits it for real through
`build_findings`, and the arm's own `verdicts`/`reasons`/`details` are handed to
the sorting rule. If `judge` were given a different sentence, or the study a
different one to match, these tests fail and the fixture-based ones do not.

The model is a stand-in that answers the planner and would be asked nothing
else; a static template is settled before any request, which the prompt count
below asserts rather than assumes. What a synthetic tree cannot give: one small
file, and no template shape nobody thought of.
"""

import json
from pathlib import Path

import compare_models
from agreement import INTERPOLATES_NOTHING, partition, reason_without_a_model
from artifacts.finding import REFUTED
from checks.semantic_probe import STATIC_REFUTATION
from checks.taint import CHECK_NAME as TAINT_CHECK
from prompt_kinds import PLANNER_PROMPT, classify
from semantic_probe_fixtures import (
    STATIC_TEMPLATE_APP, STATIC_TEMPLATE_SURFACE_ID, app_and_surfaces)

from .arm_fixtures import HOSTED, LOCAL

DECODE_SETTINGS = {"temperature": 0, "seed": 7}

# The planner is the only caller that gets to ask anything on this app, so one
# reply it can parse is the whole stand-in model.
PLANNER_REPLY = json.dumps({"order": [TAINT_CHECK]})


class RecordingAsk:
    """Stands in for a model: answers the planner and keeps every prompt it is sent."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        """Record the prompt and hand back the planner's reply."""
        self.prompts.append(prompt)
        return PLANNER_REPLY


def arm_over_the_static_app(tmp_path: Path, model: str = LOCAL) -> tuple[dict, RecordingAsk]:
    """Audit the placeholder-free app through `_arm`, exactly as the study does."""
    repo, surfaces = app_and_surfaces(tmp_path, STATIC_TEMPLATE_APP)
    ask = RecordingAsk()
    arm = compare_models._arm(model, ask, DECODE_SETTINGS, str(repo), surfaces)
    return arm, ask


def test_the_run_reached_the_template_and_asked_no_model_about_it(tmp_path) -> None:
    """Non-vacuity: one real subject, refuted, and the only prompt sent was the planner's."""
    arm, ask = arm_over_the_static_app(tmp_path)
    assert arm["verdicts"] == {STATIC_TEMPLATE_SURFACE_ID: REFUTED}
    assert arm["reasons"] == {STATIC_TEMPLATE_SURFACE_ID: None}
    assert [classify(prompt) for prompt in ask.prompts] == [PLANNER_PROMPT]


def test_the_arms_detail_is_the_sentence_the_probe_wrote(tmp_path) -> None:
    """The join between the two modules is this string, so it is asserted as itself."""
    arm, _ask = arm_over_the_static_app(tmp_path)
    assert arm["details"] == {STATIC_TEMPLATE_SURFACE_ID: STATIC_REFUTATION}


def test_a_real_refutation_is_read_back_as_interpolates_nothing(tmp_path) -> None:
    """The round trip: `judge` wrote it, `_arm` carried it, the sorting rule names it."""
    arm, _ask = arm_over_the_static_app(tmp_path)
    subject = STATIC_TEMPLATE_SURFACE_ID
    assert reason_without_a_model(arm["verdicts"][subject], arm["reasons"][subject],
                                  arm["details"][subject]) == INTERPOLATES_NOTHING


def test_two_real_runs_of_it_are_not_two_models_agreeing(tmp_path) -> None:
    """Both arms refuted it without asking, which is not a result about either model."""
    local, _local_ask = arm_over_the_static_app(tmp_path / "local", LOCAL)
    hosted, _hosted_ask = arm_over_the_static_app(tmp_path / "hosted", HOSTED)
    result = partition([local, hosted])
    assert result["not_put_to_a_model"] == [{"subject": STATIC_TEMPLATE_SURFACE_ID,
                                             "reason": INTERPOLATES_NOTHING}]
    assert result["agreements"] == [] and result["disagreements"] == []
