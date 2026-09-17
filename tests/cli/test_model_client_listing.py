"""Every model this machine has pulled, and the one listing two callers share.

`list_models` was split out of `model_digest`, which had the only copy of the
`/api/tags` parse. `web/model_routes.py` needs the same listing to say whether
the configured model is pulled, and a second parse there would be two copies of
one format across two trees -- the defect this project already records about the
JSX rebuilding a probe id.

So the split is asserted rather than described: the digest is read through
`list_models` with the transport **forbidden**, which fails if anything reaches
`/api/tags` for itself.

**Unreachable is an error here and an answer one layer up.** This module raises
`RuntimeError`, like everything else in the client; `web/model_routes.py`
catches it and answers 200 with `reachable: false`, because a 503 would be
swallowed by the page's error path. `tests/web/test_model_route.py` holds that
half.

The transport is replaced throughout, from `tests/model_server_stub.py`. No test
here reaches a server.
"""

import urllib.error

import pytest

import model_client
from model_server_stub import (
    DIGEST, MODEL_BYTES, a_model, forbid_any_request, listing, refuse, serve,
    serve_text)

OTHER_MODEL = "llama3:latest"

# A second digest, so a listing of two models has something to be confused
# about: `list_models` returns entries, and entries must not be merged.
OTHER_DIGEST = "f" * 64

# What a listing the client parses out of nothing looks like. `[]` and not an
# error: a server that answered holding no models is reachable, which is
# precisely the distinction the status route above is built on.
NOTHING_PULLED: list = []

# What the client says when the server answered something that is not a listing.
NOT_A_LISTING = "not a model listing"

# A name no server sends and every reader would sort on. Named because `7` in a
# listing reads as a typo rather than as the shape under test.
NUMERIC_NAME = 7

# Every body that is not one, named by what is wrong with it. Ollama sends none
# of these; something else listening on the port might, and each one used to
# crash a frame or two past this call rather than here.
UNREADABLE_BODIES = {
    "a bare list": [],
    "models is a string": {"models": "none"},
    # The row that makes "models is a list" load-bearing rather than tidy. A
    # string is caught anyway -- its characters are not objects, so the
    # per-entry check refuses it -- but `null` is not iterable at all, and
    # without the list check it raises `TypeError` from inside the generator,
    # which is not a `RuntimeError` and so escapes every caller here.
    "models is null": {"models": None},
    "models of strings": {"models": ["a", "b"]},
    "one bad entry among good ones": {"models": [a_model(model_client.MODEL), "a"]},
    # New in this change, and the same shape one tier down: the *entry* is an
    # object and the field its reader orders on is not a string.
    # `model_routes._named` sorts on `model["name"] or ""`, so a numeric name
    # was a `TypeError` out of the one endpoint whose job is to say whether the
    # model server is usable at all.
    "an entry whose name is a number": {
        "models": [{**a_model(model_client.MODEL), "name": NUMERIC_NAME}]},
}


# --- what the listing is ------------------------------------------------------

def test_the_listing_is_read_from_the_tag_route(monkeypatch) -> None:
    """`/api/show` does not report a listing, so the tag route is where the client looks."""
    asked = serve(monkeypatch, listing(a_model(model_client.MODEL)))
    model_client.list_models()
    assert asked == [model_client.SERVER_URL.rsplit("/", 1)[0] + "/tags"]


def test_every_model_the_server_listed_comes_back(monkeypatch) -> None:
    """Entries, not names: the status route reads a digest and a size off each one."""
    serve(monkeypatch, listing(a_model(model_client.MODEL),
                               a_model(OTHER_MODEL, digest=OTHER_DIGEST)))
    assert model_client.list_models() == [
        {"name": model_client.MODEL, "digest": DIGEST, "size": MODEL_BYTES},
        {"name": OTHER_MODEL, "digest": OTHER_DIGEST, "size": MODEL_BYTES}]


def test_a_server_holding_nothing_lists_nothing_rather_than_failing(monkeypatch) -> None:
    """Reachable and empty is an answer. It is not the same fact as unreachable."""
    serve(monkeypatch, listing())
    assert model_client.list_models() == NOTHING_PULLED


def test_a_reply_with_no_models_key_is_read_as_nothing_pulled(monkeypatch) -> None:
    """A missing key is the same answer as an empty list, not a crash mid-audit."""
    serve(monkeypatch, {})
    assert model_client.list_models() == NOTHING_PULLED


# --- and how it fails ---------------------------------------------------------

def test_an_unreachable_server_raises_and_names_the_listing_url(monkeypatch) -> None:
    """The caller degrades on RuntimeError, so that is what it must get -- with the URL in it."""
    refuse(monkeypatch, OSError("connection refused"))
    with pytest.raises(RuntimeError, match="cannot reach the local model server") as refused:
        model_client.list_models()
    assert "/api/tags" in str(refused.value)


def test_an_http_error_from_the_server_is_reported_the_same_way(monkeypatch) -> None:
    """A server answering with a status is still a server that gave no listing."""
    refuse(monkeypatch, urllib.error.HTTPError(
        model_client.SERVER_URL, 404, "Not Found", {}, None))
    with pytest.raises(RuntimeError, match="cannot reach the local model server"):
        model_client.list_models()


def test_a_listing_that_is_not_json_is_reported_the_same_way(monkeypatch) -> None:
    """Invalid json is a broken server, not a machine with no models pulled."""
    serve_text(monkeypatch, b"not json at all")
    with pytest.raises(RuntimeError, match="cannot reach the local model server"):
        model_client.list_models()


# --- and when what came back is not a listing at all ----------------------------

@pytest.mark.parametrize("body", list(UNREADABLE_BODIES.values()),
                         ids=list(UNREADABLE_BODIES))
def test_a_body_that_is_not_a_listing_is_refused_like_an_unreachable_server(
        monkeypatch, body: object) -> None:
    """Reached the server and could not read it: a third state, reported as the same refusal.

    Each of these crashed a frame or two further on instead. A body that is not
    an object raised `AttributeError` on `.get`; a `models` that is not a list
    reached every caller as something to iterate; entries that are not objects
    reached `model.get("name")`.
    """
    serve(monkeypatch, body)
    with pytest.raises(RuntimeError, match=NOT_A_LISTING):
        model_client.list_models()


def test_the_refusal_names_the_server_that_answered_it(monkeypatch) -> None:
    """A reader has to know which server to go and look at, as with every other refusal here."""
    serve(monkeypatch, {"models": "none"})
    with pytest.raises(RuntimeError) as refused:
        model_client.list_models()
    assert "/api/tags" in str(refused.value)


def test_one_unreadable_entry_refuses_the_whole_listing(monkeypatch) -> None:
    """The readable half of a listing is not an answer, and returning it is worse than refusing.

    Filtering the unreadable entries out would answer `[]` for a server that
    holds models -- "answered and holds nothing" where the truth is "answered
    and none of it could be read". Worse, callers decide whether the configured
    model is pulled by looking in this list, so a partial listing says *not
    pulled* about a model that is.
    """
    serve(monkeypatch, {"models": [a_model(model_client.MODEL), "not an object"]})
    with pytest.raises(RuntimeError, match=NOT_A_LISTING):
        model_client.list_models()


# --- the one parse, shared ----------------------------------------------------

def test_the_digest_is_read_through_the_listing_and_not_parsed_again(monkeypatch) -> None:
    """The split, asserted: the transport is forbidden, so a second parse fails here.

    A `list_models` that were merely *available* would leave `model_digest` free
    to keep its own copy of the format. Forbidding the transport is what tells
    the two apart.
    """
    forbid_any_request(monkeypatch)
    monkeypatch.setattr(model_client, "list_models",
                        lambda: [a_model(model_client.MODEL)])
    assert model_client.model_digest() == DIGEST


def test_the_digest_comes_from_whatever_the_listing_says(monkeypatch) -> None:
    """Non-vacuity for the test above: a hardcoded digest would satisfy it too."""
    forbid_any_request(monkeypatch)
    monkeypatch.setattr(model_client, "list_models",
                        lambda: [a_model(model_client.MODEL, digest=OTHER_DIGEST)])
    assert model_client.model_digest() == OTHER_DIGEST


def test_a_model_the_listing_does_not_name_has_no_digest(monkeypatch) -> None:
    """An unrecorded digest is honest; a wrong one is not. Still no second parse."""
    forbid_any_request(monkeypatch)
    monkeypatch.setattr(model_client, "list_models", lambda: [a_model(OTHER_MODEL)])
    assert model_client.model_digest() is None
