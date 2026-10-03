"""Guards on a pass's two reads of the server: the product's own, refusing what an audit records."""

import inspect
from pathlib import Path

import pytest

import eval_samples as samples
from cli.model_identity import READ_TIMEOUT_SECONDS
from council import transport
from council.transport import ModelUnavailable
from council_eval import pass_provenance
from council_eval.pass_provenance import pass_header
from council_eval.variants import BASELINE

HOST = "http://127.0.0.1:11434"


class Server:
    """A stand-in for the two reads, answering from what a test gives and noting each read."""

    def __init__(self, tags: object, version: object) -> None:
        """Hold the list of models and the version to answer with."""
        self.answers = {f"{HOST}/api/tags": tags, f"{HOST}/api/version": version}
        self.read: list[tuple[str, float]] = []

    def __call__(self, url: str, timeout: float) -> object:
        """Answer one read, or raise what a test gave in place of an answer."""
        self.read.append((url, timeout))
        answer = self.answers[url]
        if isinstance(answer, Exception):
            raise answer
        return answer


def listed(*entries: dict) -> dict:
    """Give a list of models as `/api/tags` answers."""
    return {"models": list(entries)}


def header(tmp_path, server: Server, model: str = samples.MODEL) -> dict:
    """Build the header of a pass of one model, the server answering as given."""
    dataset = tmp_path / "dataset.json"
    dataset.write_text("{}\n")
    return pass_header(model, dataset, BASELINE, get=server, run=lambda command: "")


def test_the_two_reads_are_the_audit_s_own_paths_at_the_audit_s_timeout(tmp_path):
    server = Server(listed({"name": samples.MODEL, "digest": "sha256-abc"}), {"version": "0.34.3"})
    header(tmp_path, server)
    assert server.read == [
        (f"{HOST}/api/tags", READ_TIMEOUT_SECONDS), (f"{HOST}/api/version", READ_TIMEOUT_SECONDS)
    ]


def test_a_pass_reads_the_server_through_the_product_s_transport_and_keeps_no_copy():
    assert inspect.signature(pass_header).parameters["get"].default is transport.get_json
    assert "/api/" not in Path(pass_provenance.__file__).read_text(encoding="utf-8")


def test_a_name_without_its_tag_is_refused_where_an_audit_would_assume_latest(tmp_path):
    # `cli.model_identity` reads `small` as `small:latest`; a pass is keyed by the
    # name it was asked under, so it names that name or does not start.
    untagged = samples.MODEL.split(":")[0]
    server = Server(listed({"name": f"{untagged}:latest", "digest": "d"}), {"version": "1"})
    refusal = f"the server holds no {untagged}; it has {untagged}:latest"
    with pytest.raises(ValueError, match=refusal):
        header(tmp_path, server, untagged)


def test_a_model_listed_without_a_digest_is_refused(tmp_path):
    server = Server(listed({"name": samples.MODEL}), {"version": "0.34.3"})
    with pytest.raises(ValueError, match="lists small:1b without a digest"):
        header(tmp_path, server)


def test_a_server_that_cannot_be_reached_is_refused_saying_why(tmp_path):
    gone = ModelUnavailable("http://127.0.0.1:11434/api/tags could not be reached")
    with pytest.raises(ValueError, match="a pass must name its weights, and no list of models"):
        header(tmp_path, Server(gone, {"version": "0.34.3"}))


def test_a_server_that_gives_no_version_is_refused(tmp_path):
    server = Server(listed({"name": samples.MODEL, "digest": "d"}), {"name": "ollama"})
    with pytest.raises(ValueError, match="a pass must name its server, and .* without a version"):
        header(tmp_path, server)
