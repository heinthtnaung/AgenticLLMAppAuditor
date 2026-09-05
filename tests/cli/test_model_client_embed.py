"""The client embeds text through the same local server, and says when the model is not pulled.

The transport is replaced here as in test_model_client_digest.py; no test
reaches a server. The one distinction that matters to callers is the 404: the
probe records "the embedding model is missing" for it and "the server is
unavailable" for everything else, so the two must arrive as different types.
"""

import json
import urllib.error
import urllib.request

import pytest

import model_client
from model_client import ModelNotPulled

TEXTS = ["first passage", "second passage"]
MODEL = "some-embed-model"


class FakeResponse:
    """The smallest object `urlopen` can return that `embed` will read."""

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


def stub_reply(monkeypatch, body: object) -> list:
    """Answer every request with the given JSON and return the list the requests land in."""
    sent = []

    def fake_urlopen(request, timeout=None):
        """Record the request and answer instead of sending it."""
        sent.append(request)
        return FakeResponse(json.dumps(body).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return sent


def refuse_with(monkeypatch, error: Exception) -> None:
    """Make the transport fail the way a broken or unreachable server does."""
    def fake_urlopen(request, timeout=None):
        """Raise instead of answering."""
        raise error

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


def vectors_for(texts: list[str]) -> dict:
    """A well-formed reply: one short vector per text."""
    return {"embeddings": [[0.1, 0.2, 0.3] for _ in texts]}


@pytest.mark.parametrize("texts", [[], [""], ["   "], ["fine", "\n\t"]])
def test_empty_input_is_refused_before_any_request(texts: list[str], monkeypatch) -> None:
    """No text and blank text alike fail clearly, and nothing is sent."""
    sent = stub_reply(monkeypatch, vectors_for(texts))
    with pytest.raises(ValueError, match="must be non-empty"):
        model_client.embed(texts)
    assert sent == []


def test_the_embed_endpoint_is_derived_from_the_server_url() -> None:
    """One URL setting covers every route: `/api/generate` becomes `/api/embed`."""
    assert model_client._endpoint("embed") == model_client.SERVER_URL.rsplit("/", 1)[0] + "/embed"


def test_the_request_goes_to_the_embed_route_of_the_same_server(monkeypatch) -> None:
    """Still localhost, still the configured server, a different route."""
    sent = stub_reply(monkeypatch, vectors_for(TEXTS))
    model_client.embed(TEXTS)
    assert sent[0].full_url == model_client._endpoint("embed")


def test_the_request_names_the_model_and_carries_every_text(monkeypatch) -> None:
    """Ollama's embed route takes `model` and `input`; the texts go as one batch."""
    sent = stub_reply(monkeypatch, vectors_for(TEXTS))
    model_client.embed(TEXTS, MODEL)
    assert json.loads(sent[0].data) == {"model": MODEL, "input": TEXTS}


def test_one_vector_comes_back_per_text(monkeypatch) -> None:
    """The reply's `embeddings` list is returned as-is, in the order the texts were sent."""
    stub_reply(monkeypatch, {"embeddings": [[1.0, 0.0], [0.0, 1.0]]})
    assert model_client.embed(TEXTS) == [[1.0, 0.0], [0.0, 1.0]]


def test_a_404_means_the_model_is_not_pulled(monkeypatch) -> None:
    """Ollama answers 404 for a model it has not pulled; the error names the model to pull."""
    refuse_with(monkeypatch, urllib.error.HTTPError(
        model_client._endpoint("embed"), 404, "Not Found", {}, None))
    with pytest.raises(ModelNotPulled) as refused:
        model_client.embed(TEXTS, MODEL)
    assert MODEL in str(refused.value)


def test_model_not_pulled_is_a_runtime_error() -> None:
    """Every caller that degrades on an unreachable server degrades on this too."""
    assert issubclass(ModelNotPulled, RuntimeError)


def test_another_http_status_is_a_plain_runtime_error(monkeypatch) -> None:
    """Only the 404 carries the sharper meaning; a 500 is a broken server."""
    refuse_with(monkeypatch, urllib.error.HTTPError(
        model_client._endpoint("embed"), 500, "Server Error", {}, None))
    with pytest.raises(RuntimeError, match="HTTP 500") as refused:
        model_client.embed(TEXTS)
    assert not isinstance(refused.value, ModelNotPulled)


def test_an_unreachable_server_is_a_runtime_error_naming_the_url(monkeypatch) -> None:
    """Connection refused is not a missing model."""
    refuse_with(monkeypatch, OSError("connection refused"))
    with pytest.raises(RuntimeError, match="cannot reach the local model server") as refused:
        model_client.embed(TEXTS)
    assert "/api/embed" in str(refused.value)


def test_a_reply_with_the_wrong_number_of_vectors_is_refused(monkeypatch) -> None:
    """Fewer vectors than texts would silently misalign passages and their embeddings."""
    stub_reply(monkeypatch, {"embeddings": [[0.1, 0.2]]})
    with pytest.raises(RuntimeError, match="returned 1 embeddings for 2 texts"):
        model_client.embed(TEXTS)


def test_a_reply_without_embeddings_is_refused(monkeypatch) -> None:
    """A body with no vectors is a broken server, not an empty result."""
    stub_reply(monkeypatch, {"model": MODEL})
    with pytest.raises(RuntimeError, match="returned no embeddings"):
        model_client.embed(TEXTS)


def test_the_default_model_is_the_configured_embedding_model(monkeypatch) -> None:
    """Left unnamed, the request goes to AUDITOR_EMBED_MODEL, never the chat model."""
    sent = stub_reply(monkeypatch, vectors_for(TEXTS))
    model_client.embed(TEXTS)
    assert json.loads(sent[0].data)["model"] == model_client.EMBED_MODEL
