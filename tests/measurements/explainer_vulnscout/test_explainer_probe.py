"""Guards on the explainer probe: the product's request, only the seed varied, every call kept."""

import io
import json
import sys
from itertools import product
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "measurements"))

from cli.council_run import advisory_text  # noqa: E402
from cli.explanation_run import published_on  # noqa: E402
from council.explanation_prompt import build_explanation_prompt  # noqa: E402
from council.ollama import LocalModel, build_request  # noqa: E402
from council_eval.pass_provenance import server_named  # noqa: E402
from explainer_vulnscout import probe  # noqa: E402

MODELS = ("small:1b", "other:2b")
# AV is not disputed on the first finding, so the item is dropped however a metric is read.
REPLY = json.dumps({"items": [{"metric": "AV", "why": "w", "quotation": "q"}]})


class FakeServer:
    """A stand-in for Ollama that lists the models and answers every prompt the same way."""

    def __init__(self) -> None:
        """Remember every request posted."""
        self.posted: list[dict] = []

    def post(self, url: str, payload: dict) -> dict:
        """Answer one generate request."""
        self.posted.append(payload)
        return {"model": payload["model"], "response": REPLY, "done_reason": "stop",
                "context": [1, 2, 3]}

    def get(self, url: str, timeout: float) -> dict:
        """Answer the version and the model listing."""
        if url.endswith("/api/version"):
            return {"version": "0.0.1"}
        return {"models": [{"name": one, "digest": f"digest-{one}"} for one in MODELS]}


def probed(seeds: tuple[int, ...] = (11, 12)) -> tuple[FakeServer, list[dict]]:
    """Run the probe against the fake server, and read back what it wrote."""
    server, out = FakeServer(), io.StringIO()
    probe.run(MODELS, seeds, out, server.post, server.get, lambda command: "abc\n")
    return server, [json.loads(line) for line in out.getvalue().splitlines()]


def test_every_model_is_asked_under_every_seed_about_each_disputed_finding_in_order():
    findings = probe.disputed(probe.DATASET)
    server, lines = probed()
    asked = [(one["model"], one["seed"], one["advisory_id"]) for one in lines[1:]]
    ids = [one.advisory.advisory_id for one in findings]
    expected = list(product(MODELS, (11, 12), ids))
    assert asked == expected
    assert len(server.posted) == len(expected)


def test_the_request_is_the_product_s_with_only_the_seed_chosen():
    finding = probe.disputed(probe.DATASET)[0]
    prompt = build_explanation_prompt(advisory_text(finding), published_on(finding))
    server, _ = probed(seeds=(12,))
    assert server.posted[0] == build_request(prompt, LocalModel(model=MODELS[0], seed=12))


def test_each_line_keeps_the_envelope_without_its_token_ids_and_what_explain_made_of_it():
    _, lines = probed()
    call = lines[1]
    assert call["envelope"]["response"] == REPLY
    assert "context" not in call["envelope"]
    assert call["digest"] == f"digest-{MODELS[0]}"
    assert call["outcome"]["explained"] is False
    assert [one["reason"] for one in call["outcome"]["dropped"]] == ["not a disputed metric"]


def test_the_header_names_the_weights_the_prompt_the_data_and_the_code():
    _, lines = probed()
    described = lines[0]["header"]
    assert described["digests"] == {one: f"digest-{one}" for one in MODELS}
    assert described["prompt_version"] == "sources-differ-1"
    assert described["dataset_sha256"] == probe.file_digest(probe.DATASET)
    assert (described["commit"], described["think"], described["temperature"]) == ("abc", False, 0)


def test_a_probe_on_this_machine_names_its_server_and_no_remote_host():
    described = probed()[1][0]["header"]
    assert described["server"] == "http://127.0.0.1:11434"
    assert "remote_host" not in described


def test_a_probe_on_a_server_elsewhere_names_its_server_and_its_host(remote_server):
    server, lines = probed(seeds=(11,))
    described = lines[0]["header"]
    assert (described["server"], described["remote_host"]) == (remote_server, "192.0.2.15")
    assert server.posted


def test_the_header_names_its_server_as_every_measurement_record_does(remote_server):
    # The shared fields, in their order, right after the version, where the header had them.
    described = probed(seeds=(11,))[1][0]["header"]
    named = server_named(remote_server)
    assert list(described)[:4] == ["ollama_version", "server", "remote_host", "digests"]
    assert {name: described[name] for name in named} == named


def test_a_model_the_server_does_not_list_is_refused_before_any_call():
    server = FakeServer()
    with pytest.raises(ValueError, match="holds no absent:1b"):
        probe.run(("absent:1b",), (11,), io.StringIO(), server.post, server.get, lambda command: "")
    assert server.posted == []


def test_the_probe_refuses_to_write_over_a_recorded_file(tmp_path):
    recorded = tmp_path / "replies.jsonl"
    recorded.write_text("kept\n")
    with pytest.raises(FileExistsError):
        probe.main(["small:1b", "--out", str(recorded)])
    assert recorded.read_text() == "kept\n"
