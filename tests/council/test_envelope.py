"""Guards on reading an envelope: the reply's words, or a failure that says what came back."""

import json
from itertools import chain
from pathlib import Path

import pytest

import model_shapes as shapes
from council.envelope import read_envelope
from council.ollama import LocalModel
from council.transport import ModelUnavailable

ROOT = Path(__file__).resolve().parents[2]
PINNING = LocalModel(model="any-model:1b")
# The models whose replies to the product's request are on record in this tree.
MEASURED = {"qwen2.5:7b-instruct", "llama3.2:latest", "gemma4:latest", "qwen2.5-coder:7b-instruct"}


@pytest.mark.parametrize("model", sorted(shapes.ANSWERED))
def test_a_recorded_answer_from_a_model_other_than_the_pair_is_read_as_its_words(model):
    envelope = shapes.ANSWERED[model]
    assert read_envelope(envelope, PINNING).text == envelope["response"]


def test_a_model_s_reasoning_is_never_read_as_its_answer():
    reply = read_envelope(shapes.THINKING_WITHOUT_FORMAT, PINNING)
    assert reply.text == shapes.THINKING_WITHOUT_FORMAT["response"]
    assert read_envelope(shapes.THINKS_ANYWAY, PINNING).text == shapes.ANSWER


def test_a_model_that_reasoned_until_it_was_cut_off_fails_saying_so():
    with pytest.raises(ModelUnavailable, match="cut off before it finished: 0 characters of reply"):
        read_envelope(shapes.REASONED_OUT, PINNING)


def test_an_answer_cut_off_part_way_fails_rather_than_being_read():
    said = r"cut off .* 20 characters of reply and 0 of thinking"
    with pytest.raises(ModelUnavailable, match=said):
        read_envelope(shapes.CUT_OFF, PINNING)


def test_a_model_that_only_thought_fails_naming_the_thinking_and_why_it_stopped():
    thought = {"thinking": "reasoning", "response": "", "done_reason": "stop"}
    with pytest.raises(ModelUnavailable, match="no text at all: 0 characters of reply and 9 of"):
        read_envelope(thought, PINNING)


def lines_in(pattern: str) -> list[dict]:
    """Read every JSON line of every file under the project that matches a pattern."""
    texts = (path.read_text("utf-8") for path in sorted(ROOT.glob(pattern)))
    return [json.loads(line) for line in chain.from_iterable(map(str.splitlines, texts))]


def every_recorded_envelope() -> list[dict]:
    """Give every envelope in this tree that answered the product's request."""
    passes = lines_in("measurements/council_eval_runs/*/*.replies.jsonl")
    calls = [line["envelope"] for line in passes if line["kind"] == "call" and line["envelope"]]
    probed = [line["envelope"] for line in lines_in("measurements/thinking_and_load/probe_*.jsonl")]
    return calls + probed + list(shapes.ANSWERED.values())


def test_only_these_models_have_answered_the_product_s_request_on_record():
    # A known gap, asserted so that recording another model turns this red: no
    # Qwen3, DeepSeek-R1 or other reasoning model is pulled on this machine.
    assert {envelope["model"] for envelope in every_recorded_envelope()} == MEASURED


def test_no_recorded_answer_to_the_product_s_request_carries_reasoning():
    # A known gap: every model on record either cannot think or did not under
    # `format: json`, so a thinking envelope is only ever the made-up one above.
    assert not [envelope for envelope in every_recorded_envelope() if "thinking" in envelope]
