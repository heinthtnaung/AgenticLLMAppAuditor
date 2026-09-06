"""Over a real audit, is each prompt at the `model_ask_fn` seam labelled correctly?

This is the test the other five files cannot replace. `compare_models._arm` wraps
one ask function and hands it to `build_findings`, which drives *two* callers
through it -- the planner, then the semantic probe -- and the wrapper has to read
each prompt to tell them apart. The measured defect: every prompt was filed as a
probe prompt, so a run whose only request was the planner's reported that it had
transmitted prompt template source text.

So the app is audited for real, through `_arm` itself, with a stand-in model. Two
apps, because one of them is the case that was wrong: the second has no prompt
template at all, so the planner is the only thing that asks anything, and the
exposure summary must name no template text.

What a synthetic tree cannot give: one file, no oversized source, no non-UTF-8
bytes, no template shape nobody thought of. What it does give is the seam under
a real `build_findings`, which is what was broken. Nothing here reaches a host
either -- the last test runs the same arm with every outbound connection
refused, so the study's own audit is offline apart from the ask it is handed.
"""

import json
from collections import Counter
from pathlib import Path

import compare_models
from artifacts.finding import REFUTED
from checks.taint import CHECK_NAME as TAINT_CHECK
from offline_fixtures import no_network  # noqa: F401  (used as a fixture)
from prompt_kinds import FIELD_KINDS, PLANNER_PROMPT, PROBE_PROMPT, classify
from semantic_probe_fixtures import (
    NO_PROMPT_APP, PROMPT_APP, PROMPT_SURFACE_ID, TEMPLATE_TEXT, app_and_surfaces)

MODEL_NAME = "stand-in-model"
DECODE_SETTINGS = {"temperature": 0, "seed": 7}

# The planner is asked first, so the first reply is its JSON and every later one
# is a verdict. Both are the shapes the real modules parse.
PLANNER_REPLY = json.dumps({"order": [TAINT_CHECK]})
PROBE_REPLY = "SAFE\nbecause the question is quoted away from the instructions"

# One planner prompt and one probe prompt: the app has exactly one template.
EXPECTED_PROMPTS = {PLANNER_PROMPT: 1, PROBE_PROMPT: 1}

PROBE_FIELDS = set(FIELD_KINDS[PROBE_PROMPT])
PLANNER_FIELDS = set(FIELD_KINDS[PLANNER_PROMPT])


class SequencedAsk:
    """Stands in for a model: the planner's reply first, a verdict after, prompts kept."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        """Record the prompt and answer by position, never by reading it."""
        self.prompts.append(prompt)
        return PLANNER_REPLY if len(self.prompts) == 1 else PROBE_REPLY


def run_arm(tmp_path: Path, source: str) -> tuple[dict, SequencedAsk]:
    """Audit one written-out app through `_arm`, exactly as the study does."""
    repo, surfaces = app_and_surfaces(tmp_path, source)
    ask = SequencedAsk()
    return compare_models._arm(MODEL_NAME, ask, DECODE_SETTINGS, str(repo), surfaces), ask


def test_a_run_with_a_template_sends_exactly_one_prompt_of_each_kind(tmp_path) -> None:
    """The seam carries two prompts and they are classified one apiece, not both as probes."""
    _arm_result, ask = run_arm(tmp_path, PROMPT_APP)
    assert len(ask.prompts) == 2
    assert Counter(classify(prompt) for prompt in ask.prompts) == EXPECTED_PROMPTS


def test_the_planner_is_asked_first_and_the_probe_second(tmp_path) -> None:
    """The order the stand-in model relies on, pinned rather than assumed."""
    _arm_result, ask = run_arm(tmp_path, PROMPT_APP)
    assert classify(ask.prompts[0]) == PLANNER_PROMPT
    assert classify(ask.prompts[1]) == PROBE_PROMPT
    assert TEMPLATE_TEXT in ask.prompts[1]


def test_the_ledger_counts_both_requests_and_their_bytes(tmp_path) -> None:
    """The arm's exposure is the two prompts that really left, measured not declared."""
    arm_result, ask = run_arm(tmp_path, PROMPT_APP)
    exposure = arm_result["exposure"]
    assert exposure["requests"] == 2
    assert exposure["bytes_sent"] == sum(len(prompt.encode()) for prompt in ask.prompts)
    assert exposure["prompt_kinds"] == sorted([PLANNER_PROMPT, PROBE_PROMPT])


def test_a_run_with_a_template_reports_both_sets_of_field_kinds(tmp_path) -> None:
    """Template text and surface ids both left the machine, so both are named."""
    arm_result, _ask = run_arm(tmp_path, PROMPT_APP)
    transmitted = set(arm_result["exposure"]["field_kinds_transmitted"])
    assert transmitted == PROBE_FIELDS | PLANNER_FIELDS


def test_the_probe_reached_the_one_template_the_app_has(tmp_path) -> None:
    """Non-vacuity: the model was asked about a real surface and its answer was read."""
    arm_result, _ask = run_arm(tmp_path, PROMPT_APP)
    assert arm_result["verdicts"] == {PROMPT_SURFACE_ID: REFUTED}
    assert arm_result["findings"] == []


def test_a_run_with_no_template_sends_only_the_planners_prompt(tmp_path) -> None:
    """The measured defect: nothing to probe, so one request and it is not a probe."""
    arm_result, ask = run_arm(tmp_path, NO_PROMPT_APP)
    assert len(ask.prompts) == 1
    assert classify(ask.prompts[0]) == PLANNER_PROMPT
    assert arm_result["exposure"]["requests"] == 1
    assert arm_result["exposure"]["prompt_kinds"] == [PLANNER_PROMPT]


def test_a_run_with_no_template_claims_no_template_text_was_sent(tmp_path) -> None:
    """The false statement in one line: no template existed, so none was transmitted."""
    arm_result, _ask = run_arm(tmp_path, NO_PROMPT_APP)
    transmitted = set(arm_result["exposure"]["field_kinds_transmitted"])
    assert transmitted == PLANNER_FIELDS
    assert not transmitted & PROBE_FIELDS
    assert arm_result["verdicts"] == {}


def test_an_arm_driven_by_a_stand_in_model_opens_no_socket(tmp_path, no_network) -> None:
    """The study reaches a host only through the ask function it is handed."""
    arm_result, ask = run_arm(tmp_path, PROMPT_APP)
    assert len(ask.prompts) == 2
    assert arm_result["exposure"]["requests"] == 2
    assert no_network.attempts == []
