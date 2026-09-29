"""The recorded probes hold what the docs cite of them, so a file regenerated otherwise turns red.

These read the two envelope files and nothing else: no model is asked. They pin
what the recording says, not what a model will do next time -- that is
hardware- and version-dependent, and a re-run on another machine may rightly
differ, at which point the docs citing these files need changing with them.
"""

import json
from pathlib import Path

import pytest

RECORDS = Path(__file__).resolve().parents[3] / "measurements" / "thinking_and_load"
QWEN = "qwen2.5:7b-instruct"
LLAMA = "llama3.2:latest"
GEMMA = "gemma4:latest"
LOADED = 1_000_000_000


def lines(name: str) -> list[dict]:
    """Read one recorded probe."""
    return [json.loads(line) for line in (RECORDS / name).read_text().splitlines()]


def states(model: str) -> dict[str, dict]:
    """Give one model's load-state envelopes by step."""
    own = [line for line in lines("probe_state.jsonl") if line["model"] == model]
    return {line["label"]: line["envelope"] for line in own}


def replies(model: str) -> dict[str, str]:
    """Give one model's load-state replies by step, as the server returned them."""
    return {label: envelope["response"] for label, envelope in states(model).items()}


def test_no_recorded_envelope_carries_a_thinking_field():
    recorded = lines("probe_state.jsonl") + lines("probe_think.jsonl")
    envelopes = [line["envelope"] for line in recorded]
    assert not [envelope for envelope in envelopes if "thinking" in envelope]


@pytest.mark.parametrize("model", [QWEN, LLAMA])
def test_qwen_and_llama_replied_the_same_with_and_without_think_in_one_load_state(model):
    said = replies(model)
    assert said["cold, field absent"] == said["cold, think false"]
    assert said["warm, field absent"] == said["warm, think false"]
    assert said["warm, think false"] == said["warm, think false again"]


def test_without_think_false_gemma_s_prompt_ran_two_tokens_longer_and_it_replied_otherwise():
    envelopes = states(GEMMA)
    counted = {label: envelope["prompt_eval_count"] for label, envelope in envelopes.items()}
    assert counted["cold, field absent"] == counted["warm, think true"] == 554
    assert counted["cold, think false"] == 552
    said = replies(GEMMA)
    assert said["cold, field absent"] != said["cold, think false"]
    assert said["warm, field absent"] == said["warm, think true"]


def test_qwen_replied_otherwise_cold_and_warm_in_its_confidence_alone():
    said = {label: json.loads(text) for label, text in replies(QWEN).items()}
    cold, warm = said["cold, field absent"], said["warm, field absent"]
    assert said["cold, think false"] == cold
    assert (cold["value"], cold["evidence"]) == (warm["value"], warm["evidence"])
    assert (cold["confidence"], warm["confidence"]) == ("medium", "high")


@pytest.mark.parametrize("model", [LLAMA, GEMMA])
def test_llama_and_gemma_replied_the_same_cold_and_warm(model):
    said = replies(model)
    assert said["cold, field absent"] == said["warm, field absent"]
    assert said["cold, think false"] == said["warm, think false"] == said["warm, think false again"]


def test_every_cold_call_began_with_a_load_and_no_warm_one_did():
    recorded = lines("probe_state.jsonl")
    loaded = [line["envelope"]["load_duration"] > LOADED for line in recorded]
    assert loaded == [line["label"].startswith("cold") for line in recorded]


def test_each_thinking_probe_began_from_a_load_and_its_second_call_did_not():
    loaded = [line["envelope"]["load_duration"] > LOADED for line in lines("probe_think.jsonl")]
    assert loaded == [True, False] * 3


def every_envelope() -> list[dict]:
    """Give every recorded envelope, from both probes, with its model."""
    recorded = lines("probe_think.jsonl") + lines("probe_state.jsonl")
    return [line["envelope"] for line in recorded]


@pytest.mark.parametrize("model, tokens", [(QWEN, 532), (LLAMA, 544)])
def test_qwen_and_llama_read_one_prompt_length_whatever_think_said(model, tokens):
    counted = {one["prompt_eval_count"] for one in every_envelope() if one["model"] == model}
    assert counted == {tokens}


def test_every_reply_is_47_to_55_tokens():
    assert all(47 <= one["eval_count"] <= 55 for one in every_envelope())


def test_qwen_read_its_prompt_afresh_cold_and_from_the_cache_warm():
    cached = {label: one["prompt_eval_cached_count"] for label, one in states(QWEN).items()}
    assert [count for label, count in cached.items() if label.startswith("cold")] == [0, 0]
    assert [count for label, count in cached.items() if label.startswith("warm")] == [531] * 3


def test_qwen_s_thinking_probe_replies_are_its_load_state_replies_cold_then_warm():
    thinking = [line for line in lines("probe_think.jsonl") if line["model"] == QWEN]
    said = replies(QWEN)
    assert [line["envelope"]["response"] for line in thinking] == [
        said["cold, field absent"], said["warm, think false"],
    ]
