"""Guards on what the runner records for each shape of reply a newer model may send.

Whatever comes back, a member is recorded as having answered or as having
failed with a reason that says what happened -- never as an answer nobody gave.
Each case goes the product's whole way: `council.ollama.ask`, the envelope, the
reply, and the runner's own record of the member.
"""

import io
import json
import urllib.error
from typing import Any

import pytest

import model_shapes as shapes
from council import transport
from council.answer import MemberAnswer
from council.ollama import LocalModel, ask
from council.prompt import MemberPrompt
from council.providers import AskMember
from council.roster import Member, Roster
from council.run import MetricRound
from council.runner import assess
from council.transport import Transport, post_json
from council_samples import FALLBACKS, RAW_ADVISORY, clients_of, member

URL = "http://127.0.0.1:11434/api/generate"


def asking_over(carrier: Transport) -> AskMember:
    """Build a client that asks through the product's own `ask`, over the transport given."""

    def client(asked: Member, prompt: MemberPrompt) -> str:
        """Put one prompt to the member's model and give back its words."""
        return ask(prompt, LocalModel(model=asked.model), carrier).text

    return client


def attack_vector_round(carrier: Transport) -> MetricRound:
    """Put the sample advisory to one member over a transport, and give its AV round."""
    clients = clients_of(asking_over(carrier))
    return assess(RAW_ADVISORY, Roster((member(),)), FALLBACKS, clients).rounds[0]


def answering(envelope: Any) -> Transport:
    """Build a transport that answers every request with one envelope."""
    return lambda url, payload: envelope


def failing_with(monkeypatch: pytest.MonkeyPatch, fault: Exception) -> None:
    """Make the product's own transport fail the way a real server or socket did."""

    def refuse(request: Any, timeout: float | None = None) -> Any:
        """Fail as recorded."""
        raise fault

    monkeypatch.setattr(transport.NO_PROXY_OPENER, "open", refuse)


def failure_reason(round_: MetricRound) -> str:
    """Give the reason the one member failed for, refusing a round where it did not."""
    assert round_.replies == (), f"the member was recorded as answering: {round_.replies}"
    (failure,) = round_.failures
    return failure.reason


@pytest.mark.parametrize("model", sorted(shapes.ANSWERED))
def test_a_recorded_answer_from_a_newer_model_is_recorded_as_answered(model):
    round_ = attack_vector_round(answering(shapes.ANSWERED[model]))
    assert [type(reply) for reply in round_.replies] == [MemberAnswer]
    assert round_.failures == ()


def test_a_model_that_thinks_whatever_it_is_told_is_recorded_with_its_answer_not_its_draft():
    (reply,) = attack_vector_round(answering(shapes.THINKS_ANYWAY)).replies
    assert reply.value == "N"


@pytest.mark.parametrize("shape", sorted(shapes.REFUSED))
def test_a_model_that_cannot_do_what_was_asked_is_failed_in_the_server_s_words(monkeypatch, shape):
    refused = shapes.REFUSED[shape]
    body = io.BytesIO(refused["body"].encode("utf-8"))
    failing_with(monkeypatch, urllib.error.HTTPError(URL, refused["status"], "Bad", {}, body))
    words = json.loads(refused["body"])["error"].split('" ', 1)[1]
    assert words in failure_reason(attack_vector_round(post_json))


@pytest.mark.parametrize(
    "envelope, said",
    [
        (shapes.REASONED_OUT, "cut off before it finished"),
        (shapes.CUT_OFF, "cut off before it finished"),
    ],
    ids=["reasoned until cut off", "answer cut off"],
)
def test_a_reply_that_is_no_answer_is_failed_saying_what_it_was(envelope, said):
    assert said in failure_reason(attack_vector_round(answering(envelope)))


def test_a_model_too_slow_for_the_timeout_is_failed_as_slow(monkeypatch):
    failing_with(monkeypatch, urllib.error.URLError(TimeoutError("timed out")))
    assert "did not answer within 180 s" in failure_reason(attack_vector_round(post_json))
