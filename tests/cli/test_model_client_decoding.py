"""The client sends greedy decode settings, which is what makes prose repeatable.

Separate from test_model_client.py, which refuses to fake a reply because that
would claim the client works without proving it. This file claims something
else: what the request *contains*. The transport is replaced to read the
outgoing payload, and no test here concludes anything about a server's answer.
"""

import json
import urllib.request

import model_client


class FakeResponse:
    """The smallest object `urlopen` can return that `ask` will read."""

    def __init__(self, body: bytes) -> None:
        """Hold the bytes the client will parse."""
        self.body = body

    def __enter__(self) -> "FakeResponse":
        """Support the `with urlopen(...)` the client uses."""
        return self

    def __exit__(self, *exc_info: object) -> bool:
        """Leave any exception to propagate."""
        return False

    def read(self) -> bytes:
        """Return the recorded body."""
        return self.body


def capture_request(monkeypatch) -> list:
    """Replace the transport and return the list the sent request lands in."""
    sent = []

    def fake_urlopen(request, timeout=None):
        """Record the outgoing request instead of sending it."""
        sent.append(request)
        return FakeResponse(b'{"response": "ok"}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return sent


def sent_payload(monkeypatch) -> dict:
    """Ask one question and return the JSON body the client would have sent."""
    sent = capture_request(monkeypatch)
    model_client.ask("explain this finding")
    return json.loads(sent[0].data)


def test_the_decode_settings_are_greedy_and_seeded() -> None:
    """Temperature 0 and a fixed seed are what a later run repeats."""
    assert model_client.DECODE_SETTINGS == {"temperature": 0, "seed": 0}


def test_the_settings_are_sent_with_every_prompt(monkeypatch) -> None:
    """Recorded settings mean nothing unless they are the ones actually sent."""
    assert sent_payload(monkeypatch)["options"] == model_client.DECODE_SETTINGS


def test_the_prompt_and_model_travel_with_them(monkeypatch) -> None:
    """The rest of the payload is unchanged: the same model, the same question, no streaming."""
    payload = sent_payload(monkeypatch)
    assert payload["model"] == model_client.MODEL
    assert payload["prompt"] == "explain this finding"
    assert payload["stream"] is False
