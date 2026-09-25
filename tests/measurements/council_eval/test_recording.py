"""Guards on the recording client: the product's request sent unchanged, every envelope kept."""

import pytest

import eval_samples as samples
from council.ollama import LocalModel, build_request
from council.prompt import build_prompt
from council.roster import Member
from council.transport import ModelUnavailable
from council_eval.recording import (
    NO_REQUEST,
    RecordingClient,
    request_digest,
    unload_model,
)

MEMBER = Member(samples.MODEL, "ollama", samples.MODEL, "small", runs_local=True)
PROMPT = build_prompt("AV", samples.ADVISORY_TEXT)


def ticking():
    """Give a clock that moves a second each time it is read."""
    moments = iter(range(100))
    return lambda: float(next(moments))


def test_the_client_answers_with_what_the_server_said():
    client = RecordingClient(post=samples.FakeServer(), clock=ticking())
    assert client(MEMBER, PROMPT) == samples.ANSWERS["AV"]


def test_the_request_recorded_is_the_one_the_product_builds():
    # Including `think`: the pinning under measurement is the product's, not this file's.
    server = samples.FakeServer()
    client = RecordingClient(post=server, clock=ticking())
    client(MEMBER, PROMPT)
    expected = build_request(PROMPT, LocalModel(model=samples.MODEL))
    assert server.posted == [expected]
    assert client.calls[0].request_sha256 == request_digest(expected)


def test_the_envelope_is_kept_whole_but_for_the_token_ids():
    client = RecordingClient(post=samples.FakeServer(), clock=ticking())
    client(MEMBER, PROMPT)
    assert "context" not in client.calls[0].envelope
    assert client.calls[0].envelope["load_duration"] == 2_000_000_000


def test_each_call_is_timed():
    client = RecordingClient(post=samples.FakeServer(), clock=ticking())
    client(MEMBER, PROMPT)
    assert client.calls[0].seconds == 1.0


def test_a_server_that_cannot_be_reached_is_recorded_and_still_raised():
    def unreachable(url: str, payload: dict) -> dict:
        """Fail as a server nobody is listening on would."""
        raise ModelUnavailable("connection refused")

    client = RecordingClient(post=unreachable, clock=ticking())
    with pytest.raises(ModelUnavailable):
        client(MEMBER, PROMPT)
    assert client.calls[0].envelope is None
    assert client.calls[0].request_sha256 != NO_REQUEST


def test_a_prompt_the_product_refuses_is_recorded_as_never_sent():
    overlong = build_prompt("AV", "word " * 10_000)
    client = RecordingClient(post=samples.FakeServer(), clock=ticking())
    with pytest.raises(ValueError, match="pinned to"):
        client(MEMBER, overlong)
    assert (client.calls[0].request_sha256, client.calls[0].envelope) == (NO_REQUEST, None)


def test_unloading_asks_the_server_to_keep_the_model_for_no_time():
    server = samples.FakeServer()
    unload_model(samples.MODEL, server)
    assert server.posted == [{"model": samples.MODEL, "keep_alive": 0}]


def test_a_server_that_did_not_unload_is_refused():
    with pytest.raises(RuntimeError, match="the server answered"):
        unload_model(samples.MODEL, lambda url, payload: {"done_reason": "load"})
