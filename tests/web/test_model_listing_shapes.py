"""What `GET /api/model` answers when the model server sends something it cannot read.

`test_model_route.py` holds the up/down pair: a server that answered with a
listing, and nothing listening at all. This file is the third state -- a server
that answered with something that is *not* a listing -- which the route met by
crashing. Measured before the fix, with the transport stubbed:

    proper body        -> 200
    []                 -> 500
    {"models": "none"} -> 500
    {"models": ["a"]}  -> 500

**The distinction the whole reply is built on is `null` against `[]`.** An empty
listing is `models: []` and `reachable: true` -- the server answered and holds
nothing. An unreadable one is `models: null` and `reachable: false` -- nobody
could look. Both directions are asserted here, because the first fix for this
defect collapsed them: it filtered the unreadable entries out and answered
`reachable=true, models=[]` for a body no reader could make sense of. Worse,
`configured_model_pulled` is computed from that list, so a partial listing says
*not pulled* about a model that is. One bad entry now refuses the whole listing,
and the last section of this file is what holds it there.

`UNKNOWABLE` is imported from the route rather than spelled as a literal: "not
knowable" is a named value in that module, and a test writing `None` would stop
following it.

The transport is replaced from `tests/model_server_stub.py`, which serves any
object. Nothing here opens a socket, reaches Ollama, or needs a model pulled.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from fastapi import FastAPI                                   # noqa: E402
from fastapi.testclient import TestClient                     # noqa: E402

import model_client                                           # noqa: E402
import model_routes                                           # noqa: E402

from model_server_stub import a_model, listing, serve         # noqa: E402

ROUTE = "/api/model"

# Answered whatever the model server sent, which is the point of the route.
OK = 200

# A model this machine has pulled that is neither of the configured ones, so
# "the listing could not be read" is not confused with "the model is missing".
UNRELATED_MODEL = "llama3:latest"

# What an answer nobody could read leaves unknowable. The route's own constant:
# `None` in Python, `null` on the wire, and never `false`.
UNKNOWABLE = model_routes.UNKNOWABLE

# A server that answered and holds nothing. `[]`, and reachable -- the fact the
# nulls above are not.
NOTHING_PULLED: list = []

# The sentence the client raises for a body it cannot read, carried through to
# the reply rather than replaced with a friendlier one that says less.
NOT_A_LISTING_SAID = "not a model listing"

# A name no server sends and this route sorts on. Named because `7` in a listing
# reads as a typo rather than as the shape under test.
NUMERIC_NAME = 7

# Every body that is not a listing, named by what is wrong with it. The rows
# measured as 500s, now rows of `reachable=false, models=null`.
UNREADABLE_BODIES = {
    "a bare list": [],
    "models is a string": {"models": "none"},
    # Not one of the measured 500s, and here because the guard for it is the
    # only one nothing else covers: a string is refused anyway by the per-entry
    # check, but `null` is not iterable, so without the list check the route
    # meets a `TypeError` rather than the client's `RuntimeError` -- a 500
    # again, by the same narrower-exception route as the rest of this defect.
    "models is null": {"models": None},
    "models of strings": {"models": ["a", "b"]},
    "mixed entries": {"models": [a_model(model_client.MODEL), "a"]},
    # New in this change, and the same shape one tier down: the *entry* is an
    # object and the field its reader orders on is not a string.
    # `model_routes._named` sorts on `model["name"] or ""`, so a numeric name
    # was a `TypeError` out of the one endpoint whose job is to say whether the
    # model server is usable at all.
    "an entry whose name is a number": {
        "models": [{**a_model(model_client.MODEL), "name": NUMERIC_NAME}]},
}

# The listing that makes a partial answer dangerous rather than merely wrong:
# one entry cannot be read, and the configured model is not among the ones that
# can. Dropped rather than refused, it answers "looked, and your model is not
# pulled" about a listing nobody could read.
ONE_BAD_ENTRY_BESIDE_A_GOOD_ONE = {"models": ["not an object", a_model(UNRELATED_MODEL)]}


def a_client() -> TestClient:
    """A client over an application holding the model route and nothing else."""
    app = FastAPI()
    model_routes.register(app)
    return TestClient(app)


def reply_for(monkeypatch, body: object) -> dict:
    """Ask the route with the model server answering with this exact body.

    Insists on 200: every one of these bodies is an answer about the *model*
    server, and a 5xx would be this server reporting its own failure.
    """
    serve(monkeypatch, body)
    response = a_client().get(ROUTE)
    assert response.status_code == OK, response.text
    return response.json()


# --- a listing the route could read ---------------------------------------------

def test_a_proper_listing_is_answered_with_the_models_it_holds(monkeypatch) -> None:
    """The first row, and the one that keeps every refusal below from being vacuous."""
    answered = reply_for(monkeypatch, listing(a_model(model_client.MODEL)))
    assert answered["reachable"] is True
    assert [model["name"] for model in answered["models"]] == [model_client.MODEL]


def test_an_empty_listing_is_an_answer_and_not_a_gap(monkeypatch) -> None:
    """A server that answered holding nothing: `[]`, reachable, and nothing unknowable."""
    answered = reply_for(monkeypatch, listing())
    assert answered["models"] == NOTHING_PULLED
    assert answered["models"] is not UNKNOWABLE
    assert answered["reachable"] is True


def test_an_empty_listing_still_settles_whether_the_model_is_pulled(monkeypatch) -> None:
    """Somebody looked, and it is not there: `false`, which is a result and not a gap."""
    answered = reply_for(monkeypatch, listing())
    assert answered["configured_model_pulled"] is False
    assert answered["embed_model_pulled"] is False


# --- and one it could not --------------------------------------------------------

@pytest.mark.parametrize("body", list(UNREADABLE_BODIES.values()),
                         ids=list(UNREADABLE_BODIES))
def test_a_body_that_is_not_a_listing_is_answered_as_unreachable(monkeypatch,
                                                                 body: object) -> None:
    """Each of these was a 500. Reached the server and could not read it is still an answer."""
    answered = reply_for(monkeypatch, body)
    assert answered["reachable"] is False
    assert answered["models"] is UNKNOWABLE


@pytest.mark.parametrize("body", list(UNREADABLE_BODIES.values()),
                         ids=list(UNREADABLE_BODIES))
def test_nothing_is_claimed_about_the_models_when_the_answer_was_unreadable(
        monkeypatch, body: object) -> None:
    """`false` here would be a gap rendered as a result, on the field that earns the route's keep."""
    answered = reply_for(monkeypatch, body)
    assert answered["configured_model_pulled"] is UNKNOWABLE
    assert answered["embed_model_pulled"] is UNKNOWABLE


@pytest.mark.parametrize("body", list(UNREADABLE_BODIES.values()),
                         ids=list(UNREADABLE_BODIES))
def test_the_reason_is_carried_rather_than_replaced(monkeypatch, body: object) -> None:
    """The page shows this sentence; "something went wrong" would send nobody anywhere."""
    assert NOT_A_LISTING_SAID in reply_for(monkeypatch, body)["error"]


# --- the two empties, which are not the same answer --------------------------------

def test_an_unreadable_answer_is_null_and_an_empty_one_is_a_list(monkeypatch) -> None:
    """Said as one comparison, because both are falsy and a page branching on truthiness merges them."""
    unreadable = reply_for(monkeypatch, UNREADABLE_BODIES["models of strings"])
    empty = reply_for(monkeypatch, listing())
    assert unreadable["models"] is UNKNOWABLE
    assert empty["models"] == NOTHING_PULLED
    assert unreadable["models"] != empty["models"]


def test_the_two_empties_disagree_about_whether_the_model_is_pulled(monkeypatch) -> None:
    """The other direction: `null` against `false`, which is the fact the field exists for."""
    unreadable = reply_for(monkeypatch, UNREADABLE_BODIES["models of strings"])
    empty = reply_for(monkeypatch, listing())
    assert unreadable["configured_model_pulled"] is UNKNOWABLE
    assert empty["configured_model_pulled"] is False


def test_one_unreadable_entry_refuses_the_whole_listing(monkeypatch) -> None:
    """The collapse the first fix introduced, held shut.

    Dropping the bad entry and keeping the good one answers `reachable=true`
    with a listing of one -- and `configured_model_pulled: false`, which reads
    as "looked, and it is not pulled" about an answer nobody could read.
    """
    answered = reply_for(monkeypatch, ONE_BAD_ENTRY_BESIDE_A_GOOD_ONE)
    assert answered["models"] is UNKNOWABLE
    assert answered["models"] != [{"name": UNRELATED_MODEL}]
    assert answered["configured_model_pulled"] is UNKNOWABLE


def test_a_listing_holding_the_configured_model_beside_a_bad_entry_claims_nothing(
        monkeypatch) -> None:
    """And the other way round: a partial listing must not say *pulled* either."""
    answered = reply_for(monkeypatch, UNREADABLE_BODIES["mixed entries"])
    assert answered["configured_model_pulled"] is UNKNOWABLE
    assert answered["models"] is UNKNOWABLE
