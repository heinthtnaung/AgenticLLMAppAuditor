"""Guards on the window: a prompt refused before it is sent, and one the server cut refused after.

The second guard exists because the first is an estimate. Ollama cuts a prompt
too long for the window without an error -- recorded here, three times -- so the
only proof the member read the whole advisory is the count the server reports.
"""

import json
from pathlib import Path

import pytest

import model_shapes as shapes
from council_samples import ADVISORY
from council.ollama import (
    CUT_PROMPT_FRACTION,
    LocalModel,
    build_request,
    estimated_tokens,
    read_answer,
)
from council.prompt import MemberPrompt, build_prompt
from council.transport import ModelUnavailable

# What each word of advisory adds to a prompt the tests size.
WORD = "word "
ROOT = Path(__file__).resolve().parents[2]
PROBED_STATES = ROOT / "measurements" / "thinking_and_load" / "probe_state.jsonl"
WARM_QWEN = ("qwen2.5:7b-instruct", "warm, field absent")
# Ollama's cut keeps a few tokens beyond half: 4,098 and 4,099 of 8,192, 130 of 256.
HALF_WINDOW_SLACK = 3


def prompt_estimated_at(tokens: int) -> MemberPrompt:
    """Build a prompt the guard estimates at a given number of tokens, give or take one."""
    base = estimated_tokens(build_prompt("AC", "x"))
    words = max(1, round((tokens - base) * 4 / len(WORD)))
    return build_prompt("AC", WORD * words)


def envelope_counting(counted: int) -> dict:
    """Give an envelope that answered, reporting the prompt as read at a count."""
    return {"model": "any:1b", "response": '{"value": "L"}', "done_reason": "stop",
            "prompt_eval_count": counted}


@pytest.mark.parametrize("name", sorted(shapes.CUT_PROMPTS))
def test_a_recorded_answer_to_a_prompt_the_server_cut_is_refused(name):
    cut = shapes.CUT_PROMPTS[name]
    prompt = prompt_estimated_at(cut["estimated"])
    pinning = LocalModel(model=cut["envelope"]["model"], context_tokens=cut["num_ctx"])
    counted = cut["envelope"]["prompt_eval_count"]
    with pytest.raises(ModelUnavailable, match=f"read this AC prompt as {counted} tokens"):
        read_answer(cut["envelope"], prompt, pinning)


@pytest.mark.parametrize("name", sorted(shapes.CUT_PROMPTS))
def test_ollama_cut_each_recorded_prompt_to_half_its_window_and_answered_as_if_whole(name):
    cut = shapes.CUT_PROMPTS[name]
    assert cut["envelope"]["prompt_eval_count"] <= cut["num_ctx"] // 2 + HALF_WINDOW_SLACK
    assert (cut["envelope"]["done_reason"], cut["envelope"]["response"][:1]) == ("stop", "{")


def test_a_whole_prompt_counted_above_the_estimate_is_read():
    # Gemma counted the corpus's worst prompt at 5,689 where the guard estimated 4,936.
    prompt = prompt_estimated_at(4936)
    assert read_answer(envelope_counting(5689), prompt, LocalModel()).text == '{"value": "L"}'


def test_a_cut_that_filled_the_window_instead_of_halving_it_would_not_be_caught():
    # A known gap, asserted: the check rests on the cut Ollama 0.34.3 makes, to
    # half the window. A server cutting to fill it would count about the window.
    prompt = prompt_estimated_at(6000)
    assert read_answer(envelope_counting(8100), prompt, LocalModel()).text == '{"value": "L"}'


def test_a_count_just_under_the_cut_line_is_refused_and_just_over_it_is_read():
    prompt = prompt_estimated_at(2000)
    line = estimated_tokens(prompt) * CUT_PROMPT_FRACTION
    with pytest.raises(ModelUnavailable):
        read_answer(envelope_counting(int(line) - 1), prompt, LocalModel())
    assert read_answer(envelope_counting(int(line) + 1), prompt, LocalModel())


def test_a_server_that_reports_no_count_is_not_held_to_one():
    # A known gap, asserted: nothing then shows whether the prompt was cut.
    prompt = prompt_estimated_at(2000)
    uncounted = {"model": "any:1b", "response": '{"value": "L"}', "done_reason": "stop"}
    assert read_answer(uncounted, prompt, LocalModel()).text == '{"value": "L"}'


def test_a_prompt_estimated_past_three_quarters_of_the_window_is_refused_before_sending():
    with pytest.raises(ValueError, match="is pinned to"):
        build_request(prompt_estimated_at(6300), LocalModel())
    assert build_request(prompt_estimated_at(6000), LocalModel())["prompt"]


def recorded_warm_qwen() -> dict:
    """Give the recorded envelope of Qwen asked the probe's prompt straight after itself."""
    lines = [json.loads(line) for line in PROBED_STATES.read_text("utf-8").splitlines()]
    (warm,) = [line["envelope"] for line in lines if (line["model"], line["label"]) == WARM_QWEN]
    return warm


def test_a_warm_call_counts_its_cached_tokens_so_its_whole_prompt_reads_as_whole():
    # The check assumes Ollama's count takes in the cached part of a prompt. On
    # 0.34.3 it does: 532 read, 531 of them from the cache. Were the cache left
    # out, this call would count one token and be refused as cut.
    warm = recorded_warm_qwen()
    assert (warm["prompt_eval_count"], warm["prompt_eval_cached_count"]) == (532, 531)
    reply = read_answer(warm, build_prompt("AV", ADVISORY), LocalModel())
    assert reply.text == warm["response"]
