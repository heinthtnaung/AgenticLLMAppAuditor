"""The catch-all that serves the built page, and the two things it must not swallow.

One server, one origin: FastAPI serves `frontend/dist/` and the API together.
Everything that is not the API belongs to the page, because a single-page app
routes in the browser -- so `/some/deep/link` is `index.html` and a 200, not a
404. Two exceptions, and both are the reason this file exists. A path under
`api/` is the API's to refuse, or `GET /api/audit` would answer the HTML page
with status 200: a wrong method reported as success. And a path that climbs out
of `dist/` is refused, or a URL could read this repository.

**The 404's own text is checked for staleness rather than by equality.** It used
to name "one endpoint" and there are now four -- audit, stages, runs and the
downloads -- so the sentence is read for the paths it mentions and each of those
must be a path the application really routes. Equality against a literal would
turn every new endpoint into a failing test, and asserting nothing about it is
how it came to be wrong.

**The route lives in `web/page.py`**, which owns `DIST`, `INDEX`, `ASSETS`,
the status codes and `page()`; `api.py` calls `page.register(app)` last, and
`test_page_registration.py` pins that split. The constants are read off `page`,
the application under test is still `api.app`. **Nothing here reads
`frontend/dist/`**: `page()` reads `DIST` and `INDEX` when it is called, so
every test points them at a tree it writes into `tmp_path`. That costs what
every synthetic tree costs -- the real bundle and the `/assets` mount
`register` adds only when the directory exists are both absent, and
`test_built_page_shipped.py` is what drives them.

The traversal test spells `..` percent-encoded, and the difference is the whole
test. httpx normalises `/../secret.txt` to `/secret.txt` before it leaves the
client, so a test written that way passes with the guard deleted. Sent as
`%2e%2e`, the handler really receives `../secret.txt` -- measured against a
copy of the route with the guard removed, which duly served the planted file.

The whole file skips without the server packages: with no fastapi there is
no route to exercise.
"""

import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from fastapi.testclient import TestClient    # noqa: E402

import api                                   # noqa: E402
import page                                  # noqa: E402
import run_routes                            # noqa: E402

# The build output a finished `npm run build` leaves, as much of it as a route
# test needs: the page itself and one real file beside it.
DIST_NAME = "dist"
INDEX_NAME = "index.html"
INDEX_TEXT = "<!doctype html><title>Agentic LLM-App Auditor</title><div id=root></div>"
FAVICON_NAME = "favicon.svg"
FAVICON_TEXT = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"></svg>'

# A file next to `dist/` and outside it, standing in for everything in this
# repository a URL must not be able to read.
OUTSIDE_NAME = "secret.txt"
OUTSIDE_TEXT = "not inside dist, and not the page's to serve"

# The climb, in the one spelling an HTTP client will actually transmit.
ESCAPING_PATH = f"/%2e%2e/{OUTSIDE_NAME}"

# A route the server has never heard of, which the page answers in the browser.
DEEP_LINK = "/anything/deep"

# The API's own path, and a spelling of it that does not exist.
API_PATH = "/api/audit"
API_TYPO = "/api/typo"

# A body the request rules refuse, so a POST can be shown to reach the real
# handler without an audit running: only `audit` answers this way.
NO_URL_GIVEN = {"url": ""}

# How the refusal's own sentence is read: every `/api/...` path it mentions.
API_PATH_PATTERN = re.compile(r"/api/[a-z]+")

# The prefix everything the API owns sits under, and a floor under the sweep: a
# sentence naming nothing would satisfy "every path it names exists".
API_PREFIX = "/api/"
MINIMUM_ENDPOINTS_NAMED = 3

OK = 200
JSON_TYPE = "application/json"
HTML_TYPE = "text/html"


def build_dist(tmp_path: Path) -> Path:
    """Write the built page a test serves, and one file outside it to try to reach."""
    dist = tmp_path / DIST_NAME
    dist.mkdir()
    (dist / INDEX_NAME).write_text(INDEX_TEXT, encoding="utf-8")
    (dist / FAVICON_NAME).write_text(FAVICON_TEXT, encoding="utf-8")
    (tmp_path / OUTSIDE_NAME).write_text(OUTSIDE_TEXT, encoding="utf-8")
    return dist


def point_the_route_at(monkeypatch: pytest.MonkeyPatch, dist: Path) -> Path:
    """Serve a page this test wrote instead of `frontend/dist/`, and return its index."""
    monkeypatch.setattr(page, "DIST", dist)
    monkeypatch.setattr(page, "INDEX", dist / INDEX_NAME)
    return dist / INDEX_NAME


def client_over_a_built_page(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    """A client on the app, with the page pointed at a freshly written build."""
    point_the_route_at(monkeypatch, build_dist(tmp_path))
    return TestClient(api.app)


def client_over_an_unbuilt_page(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    """A client on the app, with the page pointed at a `dist/` nobody ever built."""
    point_the_route_at(monkeypatch, tmp_path / DIST_NAME)
    return TestClient(api.app)


# --- the page -----------------------------------------------------------------

def test_the_root_returns_the_built_index(monkeypatch, tmp_path) -> None:
    """What a browser gets at the address `serve.py` prints: the page, not a listing."""
    response = client_over_a_built_page(monkeypatch, tmp_path).get("/")
    assert response.status_code == OK
    assert response.text == INDEX_TEXT


def test_a_real_file_under_dist_is_served_as_itself(monkeypatch, tmp_path) -> None:
    """A favicon is a file, not a route: the page is not returned in its place."""
    response = client_over_a_built_page(monkeypatch, tmp_path).get(f"/{FAVICON_NAME}")
    assert response.status_code == OK
    assert response.text == FAVICON_TEXT


def test_an_unknown_deep_link_returns_the_page_and_not_a_404(monkeypatch, tmp_path) -> None:
    """A single-page app routes in the browser, so a link the server never heard of is the page."""
    response = client_over_a_built_page(monkeypatch, tmp_path).get(DEEP_LINK)
    assert response.status_code == OK
    assert response.text == INDEX_TEXT


# --- the climb out of dist ----------------------------------------------------

def test_a_traversal_does_not_escape_dist(monkeypatch, tmp_path) -> None:
    """A URL that climbs out of the build answers with the page, never with what it asked for."""
    response = client_over_a_built_page(monkeypatch, tmp_path).get(ESCAPING_PATH)
    assert response.status_code == OK
    assert response.text == INDEX_TEXT
    assert OUTSIDE_TEXT not in response.text


def test_the_file_the_traversal_asked_for_was_really_there(tmp_path) -> None:
    """Non-vacuity: the guard refused a file that exists, not one that was never written."""
    build_dist(tmp_path)
    assert (tmp_path / OUTSIDE_NAME).read_text(encoding="utf-8") == OUTSIDE_TEXT


def test_the_handler_itself_refuses_the_climb(monkeypatch, tmp_path) -> None:
    """The guard, not the client: called directly, `..` cannot be normalised away first."""
    index = point_the_route_at(monkeypatch, build_dist(tmp_path))
    answered = page.page(f"../{OUTSIDE_NAME}")
    assert Path(answered.path) == index


# --- the page that was never built --------------------------------------------

def test_an_unbuilt_page_answers_service_unavailable(monkeypatch, tmp_path) -> None:
    """503, not 404: the address is right and the server simply cannot answer it yet."""
    response = client_over_an_unbuilt_page(monkeypatch, tmp_path).get("/")
    assert response.status_code == page.NO_BUILD_YET


def test_an_unbuilt_page_says_how_to_build_it(monkeypatch, tmp_path) -> None:
    """The one failure this server can fully explain, so it explains it in the browser."""
    response = client_over_an_unbuilt_page(monkeypatch, tmp_path).get("/")
    assert "has not been built yet" in response.text
    assert "npm run build" in response.text


# --- what the catch-all does not swallow --------------------------------------

def test_a_post_reaches_the_api_and_not_the_page(monkeypatch, tmp_path) -> None:
    """The pair that matters: the prefix guard must not shadow the endpoint it protects.

    A refused body is used rather than a stubbed audit, so nothing runs: 400 is
    an answer only `audit` gives. The page would have answered 405 to a POST.
    """
    client = client_over_a_built_page(monkeypatch, tmp_path)
    assert client.post(API_PATH, json=NO_URL_GIVEN).status_code == run_routes.REFUSED


def test_a_get_on_the_api_path_is_a_404_and_not_the_page(monkeypatch, tmp_path) -> None:
    """A wrong method used to be answered with the HTML page and status 200."""
    response = client_over_a_built_page(monkeypatch, tmp_path).get(API_PATH)
    assert response.status_code == page.NO_SUCH_ENDPOINT
    assert JSON_TYPE in response.headers["content-type"]
    assert HTML_TYPE not in response.headers["content-type"]


def test_an_unknown_api_path_is_a_404_and_not_the_page(monkeypatch, tmp_path) -> None:
    """Everything under the prefix is the API's, including spellings it does not have."""
    response = client_over_a_built_page(monkeypatch, tmp_path).get(API_TYPO)
    assert response.status_code == page.NO_SUCH_ENDPOINT
    assert JSON_TYPE in response.headers["content-type"]


def test_the_api_refusal_names_endpoints_that_really_exist(monkeypatch, tmp_path) -> None:
    """A 404 with no reason reads as a broken deploy; this one may not name a stale route."""
    response = client_over_a_built_page(monkeypatch, tmp_path).get(API_TYPO)
    named = API_PATH_PATTERN.findall(response.json()["detail"])
    routed = [route.path for route in api.app.routes if hasattr(route, "path")]
    assert [path for path in named
            if not any(real.startswith(path) for real in routed)] == []


def test_the_api_refusal_names_more_than_one_endpoint(monkeypatch, tmp_path) -> None:
    """Non-vacuity, and the drift itself: this sentence said "one endpoint" after there were four."""
    response = client_over_a_built_page(monkeypatch, tmp_path).get(API_TYPO)
    named = API_PATH_PATTERN.findall(response.json()["detail"])
    assert len(named) >= MINIMUM_ENDPOINTS_NAMED
    assert all(path.startswith(API_PREFIX) for path in named)


def test_an_unbuilt_page_still_refuses_an_api_path(monkeypatch, tmp_path) -> None:
    """The prefix is refused before the build is looked for, so the two answers cannot swap."""
    response = client_over_an_unbuilt_page(monkeypatch, tmp_path).get(API_TYPO)
    assert response.status_code == page.NO_SUCH_ENDPOINT
