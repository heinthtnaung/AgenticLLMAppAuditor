"""Which module attaches the page's routes, and what registering them last buys.

`web/api.py` was doing two jobs; the static-page half is now `web/page.py`, and
`api.py` ends with `page.register(app)`. This file pins that wiring: `register`
is what attaches the catch-all and the `/assets` mount, and the handler the
application actually serves is `page.page` itself rather than a copy left
behind. `test_page_route.py` asserts what those routes *answer*; this asserts
where they came from.

**What the order really buys, measured rather than assumed.** `api.py`'s
closing comment says the catch-all is registered last "so it does not swallow
`/api/audit`". Reversed, the POST is *not* swallowed: the catch-all is declared
with `app.get`, so a POST is only a partial match and Starlette keeps looking
until it finds the full one. What reversal does cost is any `GET` under
`/api/`, which the catch-all matches fully and answers with its own 404. All
three facts are asserted below, so the comment is held to what is true and not
to what it says. Today `POST /api/audit` is the only endpoint, so the guard
that keeps `GET /api/audit` from returning the HTML page is `API_PREFIX` inside
`page()` -- not this ordering.

The whole file skips without the server packages: with no fastapi there is
nothing to register onto.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from fastapi import FastAPI                  # noqa: E402
from fastapi.testclient import TestClient    # noqa: E402

import api                                   # noqa: E402
import page                                  # noqa: E402

# The two routes `register` is responsible for, spelled as starlette stores them.
CATCH_ALL = "/{path:path}"
ASSETS_MOUNT = "/assets"

# The API's one endpoint, and a GET spelling under the same prefix. The second
# exists only to be shadowed: the API has no GET route today.
API_PATH = "/api/audit"

# A body the request rules refuse, so the POST is shown to reach the endpoint
# without an audit running.
NO_URL_GIVEN = {"url": ""}

OK = 200
NOT_FOUND = 404

# What a stand-in endpoint answers, so "the endpoint was reached" is not
# confused with "something answered 200".
REACHED = {"reached": True}


def routed_paths(app: FastAPI) -> list[str]:
    """Every path an application routes, in the order they were registered."""
    return [route.path for route in app.routes if hasattr(route, "path")]


def stand_in_endpoint() -> dict:
    """An endpoint under `/api/`, standing in for one the API might grow."""
    return REACHED


def app_with_the_page_registered_first() -> FastAPI:
    """A fresh application in the wrong order: the catch-all, then the API."""
    reversed_app = FastAPI()
    page.register(reversed_app)
    reversed_app.get(API_PATH)(stand_in_endpoint)
    reversed_app.post(API_PATH)(stand_in_endpoint)
    return reversed_app


def app_with_the_page_registered_last() -> FastAPI:
    """A fresh application in `api.py`'s order: the API, then the catch-all."""
    ordered = FastAPI()
    ordered.get(API_PATH)(stand_in_endpoint)
    page.register(ordered)
    return ordered


# --- what `register` attaches -------------------------------------------------

def test_the_catch_all_is_attached_by_the_page_module(monkeypatch, tmp_path) -> None:
    """The split itself: a fresh application has no catch-all until `register` runs."""
    monkeypatch.setattr(page, "ASSETS", tmp_path / "assets")
    fresh = FastAPI()
    assert CATCH_ALL not in routed_paths(fresh)
    page.register(fresh)
    assert CATCH_ALL in routed_paths(fresh)


def test_the_catch_all_the_application_serves_is_the_page_modules_own(monkeypatch,
                                                                      tmp_path) -> None:
    """The handler moved, rather than being copied: the route is `page.page` itself."""
    monkeypatch.setattr(page, "ASSETS", tmp_path / "assets")
    fresh = FastAPI()
    page.register(fresh)
    attached = [route for route in fresh.routes if getattr(route, "path", "") == CATCH_ALL]
    assert [route.endpoint for route in attached] == [page.page]


def test_the_running_application_serves_that_same_handler() -> None:
    """`api.app` is wired by `register` too, not by a second declaration in `api.py`."""
    attached = [route for route in api.app.routes if getattr(route, "path", "") == CATCH_ALL]
    assert [route.endpoint for route in attached] == [page.page]


def test_the_assets_mount_is_attached_when_a_build_is_there(monkeypatch, tmp_path) -> None:
    """The built bundle is served from a mount, and `register` is what adds it."""
    built = tmp_path / "assets"
    built.mkdir()
    monkeypatch.setattr(page, "ASSETS", built)
    fresh = FastAPI()
    page.register(fresh)
    assert ASSETS_MOUNT in routed_paths(fresh)


def test_no_assets_mount_is_attached_when_the_page_was_never_built(monkeypatch,
                                                                   tmp_path) -> None:
    """`StaticFiles` raises on a missing directory, which would stop the API starting at all."""
    monkeypatch.setattr(page, "ASSETS", tmp_path / "never-built")
    fresh = FastAPI()
    page.register(fresh)
    assert ASSETS_MOUNT not in routed_paths(fresh)


# --- the order, and what it actually costs to reverse -------------------------

def test_the_api_route_is_registered_before_the_catch_all() -> None:
    """`api.py` calls `register` last, and starlette matches in registration order."""
    paths = routed_paths(api.app)
    assert paths.index(API_PATH) < paths.index(CATCH_ALL)


def test_a_get_under_the_api_prefix_is_shadowed_when_the_page_goes_first(
        monkeypatch, tmp_path) -> None:
    """What reversing really costs: the catch-all matches the GET fully and answers first."""
    monkeypatch.setattr(page, "ASSETS", tmp_path / "assets")
    response = TestClient(app_with_the_page_registered_first()).get(API_PATH)
    assert response.status_code == NOT_FOUND
    assert response.json() != REACHED


def test_that_same_get_is_reached_when_the_page_is_registered_last(monkeypatch,
                                                                   tmp_path) -> None:
    """Non-vacuity: the 404 above is the ordering, not a route that was never added."""
    monkeypatch.setattr(page, "ASSETS", tmp_path / "assets")
    response = TestClient(app_with_the_page_registered_last()).get(API_PATH)
    assert response.status_code == OK
    assert response.json() == REACHED


def test_a_post_survives_the_reversed_order(monkeypatch, tmp_path) -> None:
    """The correction to the comment: `app.get` leaves a POST a partial match, not a swallowed one.

    Asserted so nobody removes the `API_PREFIX` guard believing this ordering
    protects `/api/audit`. It does not: the endpoint is a POST, and the thing
    that keeps `GET /api/audit` off the HTML page is that guard.
    """
    monkeypatch.setattr(page, "ASSETS", tmp_path / "assets")
    response = TestClient(app_with_the_page_registered_first()).post(API_PATH,
                                                                    json=NO_URL_GIVEN)
    assert response.status_code == OK
    assert response.json() == REACHED
