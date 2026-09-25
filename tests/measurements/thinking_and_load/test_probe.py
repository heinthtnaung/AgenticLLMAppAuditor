"""Guards on the probe: the product's request with only `think` varied, and cold steps unloaded."""

import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
# The probe sits beside the other measurement scripts; its advisory is the council samples'.
sys.path.insert(0, str(ROOT / "measurements"))
sys.path.insert(0, str(ROOT / "tests" / "council"))

import council_samples  # noqa: E402
from council.ollama import LocalModel, build_request  # noqa: E402
from council.prompt import build_prompt  # noqa: E402
from thinking_and_load import probe  # noqa: E402

PINNING = LocalModel(model="qwen2.5:7b-instruct")
RECORDED_STATES = ROOT / "measurements" / "thinking_and_load" / "probe_state.jsonl"


class FakeServer:
    """A stand-in for Ollama that unloads when asked and answers every prompt the same way."""

    def __init__(self, unload_answer: str = probe.UNLOADED) -> None:
        """Remember every request, and say what an unload request is answered with."""
        self.unload_answer = unload_answer
        self.posted: list[dict] = []

    def __call__(self, url: str, payload: dict) -> dict:
        """Answer one request."""
        self.posted.append(payload)
        if "prompt" not in payload:
            return {"done_reason": self.unload_answer}
        return {"response": "{}", "context": [1, 2, 3]}


def probed(
    name: str, steps: tuple[probe.Step, ...], models: tuple[str, ...] = ("m",)
) -> tuple[FakeServer, list[dict]]:
    """Run one probe over its models against the fake server, and read back what it wrote."""
    server, out = FakeServer(), io.StringIO()
    probe.run(name, steps, models, out, server)
    return server, [json.loads(line) for line in out.getvalue().splitlines()]


def test_the_probe_asks_about_the_advisory_the_recorded_probes_asked_about():
    assert probe.ADVISORY == council_samples.ADVISORY


def test_with_think_absent_the_request_is_the_product_s_without_the_field():
    expected = build_request(build_prompt("AV", probe.ADVISORY), PINNING)
    del expected["think"]
    assert probe.request_for(probe.ABSENT, PINNING) == expected


@pytest.mark.parametrize("think, sent", [(probe.FALSE, False), (probe.TRUE, True)])
def test_with_think_set_the_field_is_all_that_differs(think, sent):
    request = probe.request_for(think, PINNING)
    assert request.pop("think") is sent
    assert request == probe.request_for(probe.ABSENT, PINNING)


def test_a_cold_step_unloads_the_probed_models_itself_included_and_a_warm_step_does_not():
    server, _ = probed(probe.LOAD_STATE, probe.STEPS[probe.LOAD_STATE][:3], ("m", "n"))
    kind = {True: "ask", False: "unload"}
    asked = [f"{kind['prompt' in payload]} {payload['model']}" for payload in server.posted]
    assert asked == [
        "unload m", "unload n", "ask m", "ask m", "ask m",
        "unload m", "unload n", "ask n", "ask n", "ask n",
    ]


def test_a_load_state_call_is_written_as_recorded_without_the_token_ids():
    _, lines = probed(probe.LOAD_STATE, probe.STEPS[probe.LOAD_STATE][:1])
    assert lines == [{"model": "m", "label": "cold, field absent", "envelope": {"response": "{}"}}]


def test_a_thinking_call_is_named_by_its_think_setting_as_recorded():
    _, lines = probed(probe.THINKING, probe.STEPS[probe.THINKING])
    assert [line["think"] for line in lines] == [probe.ABSENT, probe.FALSE]


def test_the_load_state_steps_are_the_ones_recorded_in_their_order():
    lines = [json.loads(line) for line in RECORDED_STATES.read_text().splitlines()]
    gemma = [line["label"] for line in lines if line["model"] == "gemma4:latest"]
    assert gemma == [step.label for step in (*probe.STEPS[probe.LOAD_STATE], probe.THINK_TRUE)]


def test_a_server_that_does_not_unload_is_refused():
    with pytest.raises(RuntimeError, match="the server answered"):
        probe.unload_every_model(FakeServer(unload_answer="load"), ("m",))


def test_a_recorded_file_is_never_written_over(tmp_path):
    taken = tmp_path / "probe_state.jsonl"
    taken.write_text("recorded\n")
    with pytest.raises(FileExistsError):
        probe.main([probe.LOAD_STATE, "m", "--out", str(taken)])
