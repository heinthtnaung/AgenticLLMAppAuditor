"""The client reports the model's content digest, so a mutable tag is not the only record.

One of the models compared is literally `:latest`, which names a different build
after the next pull, so a run recorded by tag alone is repeatable only until
someone re-pulls. The digest comes from the server's tag listing, which is where
Ollama reports it. The transport is replaced here; no test reaches a server.

**This file drives the whole chain, transport included.** The listing itself,
and the claim that `model_digest` reads it rather than parsing `/api/tags` a
second time, are `test_model_client_listing.py` -- which forbids the transport
in order to say so. The fake server they share is `tests/model_server_stub.py`:
four copies of one fake response is how the four copies come to disagree.
"""

import urllib.error

import pytest

import model_client
from model_server_stub import DIGEST, refuse, serve, serve_text

OTHER_MODEL = "llama3:latest"


def stub_listing(monkeypatch, body: object) -> list[str]:
    """Serve a fixed tag listing and return the list the requested URL lands in."""
    return serve(monkeypatch, body)


def listing_with(*names: str) -> dict:
    """A tag listing naming each model, all sharing one digest."""
    return {"models": [{"name": name, "digest": DIGEST} for name in names]}


def test_the_digest_is_read_from_the_tag_listing(monkeypatch) -> None:
    """`/api/show` does not report it, so the tag listing is where the client looks."""
    asked = stub_listing(monkeypatch, listing_with(model_client.MODEL))
    model_client.model_digest()
    assert asked[0].endswith("/api/tags")


def test_the_listing_is_read_from_the_same_local_server(monkeypatch) -> None:
    """Still localhost, still offline: the URL is derived from the configured one."""
    asked = stub_listing(monkeypatch, listing_with(model_client.MODEL))
    model_client.model_digest()
    assert asked[0] == model_client.SERVER_URL.rsplit("/", 1)[0] + "/tags"


def test_the_configured_models_digest_is_returned(monkeypatch) -> None:
    """The digest belongs to the model this run would actually send prompts to."""
    stub_listing(monkeypatch, listing_with(OTHER_MODEL, model_client.MODEL))
    assert model_client.model_digest() == DIGEST


def test_a_model_the_server_has_not_pulled_has_no_digest(monkeypatch) -> None:
    """An unrecorded digest is honest; a wrong one is not."""
    stub_listing(monkeypatch, listing_with(OTHER_MODEL))
    assert model_client.model_digest() is None


def test_a_server_listing_nothing_yields_no_digest(monkeypatch) -> None:
    """A missing `models` key is the same answer as an empty one, not a crash."""
    stub_listing(monkeypatch, {})
    assert model_client.model_digest() is None


def test_a_listed_model_with_no_digest_yields_none(monkeypatch) -> None:
    """Null is what the provenance block accepts, so the client may return it."""
    stub_listing(monkeypatch, {"models": [{"name": model_client.MODEL}]})
    assert model_client.model_digest() is None


def refuse_with(monkeypatch, error: Exception) -> None:
    """Make the transport fail the way an unreachable or broken server does."""
    refuse(monkeypatch, error)


def test_an_unreachable_server_raises_and_names_the_listing_url(monkeypatch) -> None:
    """The caller degrades the artifact on RuntimeError, so that is what it must get."""
    refuse_with(monkeypatch, OSError("connection refused"))
    with pytest.raises(RuntimeError, match="cannot reach the local model server") as refused:
        model_client.model_digest()
    assert "/api/tags" in str(refused.value)


def test_an_http_error_from_the_server_is_reported_the_same_way(monkeypatch) -> None:
    """A server answering with a status is still a server that gave no digest."""
    refuse_with(monkeypatch, urllib.error.HTTPError(
        model_client.SERVER_URL, 404, "Not Found", {}, None))
    with pytest.raises(RuntimeError, match="cannot reach the local model server"):
        model_client.model_digest()


def test_a_listing_that_is_not_json_is_reported_the_same_way(monkeypatch) -> None:
    """Invalid json is a broken server, not a model without a digest."""
    serve_text(monkeypatch, b"not json at all")
    with pytest.raises(RuntimeError, match="cannot reach the local model server"):
        model_client.model_digest()
