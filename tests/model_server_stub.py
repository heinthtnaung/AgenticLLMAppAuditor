"""A local model server that never answered, and the three ways it can fail.

`model_client.list_models` reads Ollama's `/api/tags` with `urllib.request`, and
two files now need to drive it without a socket: the client's own tests, and the
`GET /api/model` route in `web/`, which reports *unreachable* as an answer
rather than as a failure and therefore has to be shown both paths.

The transport is what is replaced, not the client: every test through here still
builds the URL, parses the body and raises the client's own errors. Nothing here
opens a connection, and `forbid_any_request` turns an attempt into a failure
rather than a wait.

Nothing here asserts anything. It serves a listing, or refuses to.
"""

import json
import urllib.request

import pytest

# Bare hex, as Ollama's /api/tags really reports it. This module builds the
# server's own reply, so a prefixed value here would be a shape no server sends.
DIGEST = "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

# What a listed model really carries, so a test reads the keys the page reads.
MODEL_BYTES = 4_683_075_271


class FakeResponse:
    """The smallest object `urlopen` can return that the client will read."""

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


def serve(monkeypatch: pytest.MonkeyPatch, body: object) -> list[str]:
    """Answer every request with one fixed body, and return the URLs that were asked for."""
    asked: list[str] = []

    def fake_urlopen(url, timeout=None):
        """Record the URL and answer with the given body instead of sending it."""
        asked.append(url)
        return FakeResponse(json.dumps(body).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return asked


def serve_text(monkeypatch: pytest.MonkeyPatch, text: bytes) -> None:
    """Answer with bytes that are not JSON, which is a broken server rather than an empty one."""
    def fake_urlopen(url, timeout=None):
        """Answer with something no json parser will read."""
        return FakeResponse(text)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


def refuse(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    """Make the transport fail the way an unreachable or broken server does."""
    def fake_urlopen(url, timeout=None):
        """Raise instead of answering."""
        raise error

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


def forbid_any_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any attempt to open a connection a test failure, not a wait on a socket."""
    def fake_urlopen(url, timeout=None):
        """Fail loudly: reaching here means the code under test opened a connection."""
        raise AssertionError(f"the code under test asked the network for {url}")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


def listing(*models: dict) -> dict:
    """One `/api/tags` reply holding these models, in the shape Ollama sends."""
    return {"models": list(models)}


def a_model(name: str, digest: str = DIGEST, size: int = MODEL_BYTES) -> dict:
    """One entry of a tag listing, with the three keys the status route reads."""
    return {"name": name, "digest": digest, "size": size}
