"""Whether the local model server is up, and the two nulls that answer are not.

`GET /api/model` exists because a configured model that is not pulled fails
*mid-run*, after the repository has already been cloned. Saying so before anyone
starts is the whole point, and it puts three distinctions on the route that this
file is mostly about:

- **200 even when Ollama is down.** This server answered; the model server did
  not. A 503 would be swallowed by the page's error path, which keeps only
  `detail` -- turning a stopped model server into a generic failure, which is
  the gap-rendered-as-noise the reply exists to prevent.
- **`models` is `null` when nobody could ask and `[]` when the server answered
  holding nothing.** The same rule `findings: null` carries against
  `findings: []`, on a route where it is easy to collapse and impossible to
  recover afterwards.
- **`configured_model_pulled` is `null` when unreachable and `false` when
  reachable and not pulled.** "Not pulled" said when nobody looked is a gap
  rendered as a result.

The transport is replaced from `tests/model_server_stub.py`, so both
reachability paths run through the real `model_client.list_models` and neither
opens a socket. That the route reaches Ollama *only* through that client is
`test_web_offline_containment.py`.

The whole file skips without the server packages: with no fastapi there is no
route to ask.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from fastapi import FastAPI                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

import model_client                                # noqa: E402
import model_routes                                # noqa: E402
from run_record import REPLY_SCHEMA_VERSION        # noqa: E402

from model_server_stub import (                    # noqa: E402
    DIGEST, MODEL_BYTES, a_model, listing, refuse, serve)

ROUTE = "/api/model"

# Answered whatever the model server does, which is the point of the route.
OK = 200

# Every key the reply carries, named so a test holds the set rather than
# trusting the serialiser. A key added without a version bump is caught here.
EXPECTED_KEYS = {"schema_version", "reachable", "error", "models",
                 "configured_model", "configured_model_pulled",
                 "embed_model", "embed_model_pulled"}

# What each listed model is reduced to: the three facts the page shows, and no
# others -- a tag listing carries a `modified_at` and a whole `details` block
# that nothing here has a use for.
EXPECTED_MODEL_KEYS = {"name", "digest", "bytes"}

# A model the machine has pulled that is neither of the configured ones, so
# "reachable" and "holds the right model" are told apart.
UNRELATED_MODEL = "llama3:latest"

# Two names that sort the other way round from the order they are served in, so
# a route that passed the listing through unsorted fails rather than looks right.
FIRST_BY_NAME = "aardvark:latest"
LAST_BY_NAME = "zebra:latest"

# What an unreachable server leaves unknowable. `None` in Python, `null` on the
# wire, and never `false`.
UNKNOWABLE = None

# The sentence `model_client` raises, which the reply carries rather than
# replacing with a friendlier one that says less.
UNREACHABLE_MESSAGE = "cannot reach the local model server"


def a_client() -> TestClient:
    """A client over an application holding the model route and nothing else."""
    app = FastAPI()
    model_routes.register(app)
    return TestClient(app)


def status(monkeypatch, *models: dict) -> dict:
    """Ask the route with the model server answering with these models."""
    serve(monkeypatch, listing(*models))
    response = a_client().get(ROUTE)
    assert response.status_code == OK, response.text
    return response.json()


def status_with_no_server(monkeypatch) -> dict:
    """Ask the route with nothing listening where the model server should be."""
    refuse(monkeypatch, OSError("connection refused"))
    response = a_client().get(ROUTE)
    assert response.status_code == OK, response.text
    return response.json()


# --- the shape of the reply ----------------------------------------------------

def test_the_reply_holds_exactly_the_documented_keys(monkeypatch) -> None:
    """Named rather than trusted, so a key added without a version bump is caught."""
    assert set(status(monkeypatch, a_model(model_client.MODEL))) == EXPECTED_KEYS


def test_an_unreachable_server_answers_with_the_same_keys(monkeypatch) -> None:
    """One parser for both paths: the page must not need two shapes for two outcomes."""
    assert set(status_with_no_server(monkeypatch)) == EXPECTED_KEYS


def test_the_reply_carries_the_version_everything_under_api_carries(monkeypatch) -> None:
    """One constant, so three bodies cannot claim three versions."""
    answered = status(monkeypatch, a_model(model_client.MODEL))
    assert answered["schema_version"] == REPLY_SCHEMA_VERSION


def test_the_configured_names_are_the_clients_own(monkeypatch) -> None:
    """Read off `model_client`, so the page reports the model an audit would really use."""
    answered = status(monkeypatch, a_model(model_client.MODEL))
    assert answered["configured_model"] == model_client.MODEL
    assert answered["embed_model"] == model_client.EMBED_MODEL


# --- a server that answered ----------------------------------------------------

def test_a_reachable_server_says_so_and_carries_no_error(monkeypatch) -> None:
    """`error` is null exactly when there was nothing to report."""
    answered = status(monkeypatch, a_model(model_client.MODEL))
    assert answered["reachable"] is True
    assert answered["error"] is None


def test_each_listed_model_is_reduced_to_the_three_facts_the_page_shows(monkeypatch) -> None:
    """A tag listing carries more; the reply carries the name, the digest and the size."""
    answered = status(monkeypatch, a_model(model_client.MODEL))
    assert [set(model) for model in answered["models"]] == [EXPECTED_MODEL_KEYS]
    assert answered["models"] == [
        {"name": model_client.MODEL, "digest": DIGEST, "bytes": MODEL_BYTES}]


def test_the_models_are_sorted_by_name_so_the_list_does_not_jump(monkeypatch) -> None:
    """Served in the other order, so a passed-through listing fails rather than looks right."""
    answered = status(monkeypatch, a_model(LAST_BY_NAME), a_model(FIRST_BY_NAME))
    assert [model["name"] for model in answered["models"]] == [FIRST_BY_NAME, LAST_BY_NAME]


def test_the_configured_model_being_pulled_is_established(monkeypatch) -> None:
    """The clean state, and the only one an audit can start from."""
    answered = status(monkeypatch, a_model(model_client.MODEL),
                      a_model(model_client.EMBED_MODEL))
    assert answered["configured_model_pulled"] is True
    assert answered["embed_model_pulled"] is True


def test_a_reachable_server_without_the_model_says_false_and_not_null(monkeypatch) -> None:
    """The distinction the route exists for: looked, and it is not there."""
    answered = status(monkeypatch, a_model(UNRELATED_MODEL))
    assert answered["configured_model_pulled"] is False
    assert answered["embed_model_pulled"] is False
    assert answered["reachable"] is True


def test_a_server_holding_nothing_lists_nothing_rather_than_null(monkeypatch) -> None:
    """`[]` is an answer -- the server is up and has no models -- and `null` is a gap."""
    answered = status(monkeypatch)
    assert answered["models"] == []
    assert answered["models"] is not UNKNOWABLE
    assert answered["configured_model_pulled"] is False


# --- a server that did not ------------------------------------------------------

def test_a_stopped_model_server_is_still_answered_with_200(monkeypatch) -> None:
    """This server answered. A 503 would be read by the page as *this* server failing."""
    refuse(monkeypatch, OSError("connection refused"))
    assert a_client().get(ROUTE).status_code == OK


def test_an_unreachable_server_is_reported_as_unreachable(monkeypatch) -> None:
    """The fact the pill renders, carried as a field rather than inferred from a status."""
    assert status_with_no_server(monkeypatch)["reachable"] is False


def test_an_unreachable_server_carries_the_clients_own_sentence(monkeypatch) -> None:
    """It names the fix -- start the server -- so it is shown rather than replaced."""
    assert UNREACHABLE_MESSAGE in status_with_no_server(monkeypatch)["error"]


def test_nothing_about_the_models_is_claimed_when_nobody_could_look(monkeypatch) -> None:
    """The three nulls together: `false` here would be a gap rendered as a result."""
    answered = status_with_no_server(monkeypatch)
    assert answered["models"] is UNKNOWABLE
    assert answered["configured_model_pulled"] is UNKNOWABLE
    assert answered["embed_model_pulled"] is UNKNOWABLE


def test_the_two_empty_answers_are_not_the_same_answer(monkeypatch) -> None:
    """Non-vacuity for both sets of nulls above, said as one comparison.

    A route that collapsed the two would pass every test that read only one of
    them: `[]` and `null` are both falsy, and a page that branched on truthiness
    would render a stopped server as a machine with no models pulled.
    """
    assert status(monkeypatch)["models"] != status_with_no_server(monkeypatch)["models"]


def test_the_configured_names_are_still_reported_when_nobody_answered(monkeypatch) -> None:
    """They are this machine's settings, not the model server's, so they are always knowable."""
    answered = status_with_no_server(monkeypatch)
    assert answered["configured_model"] == model_client.MODEL
    assert answered["embed_model"] == model_client.EMBED_MODEL
