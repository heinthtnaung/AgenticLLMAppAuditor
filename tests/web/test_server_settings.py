"""The address the server binds, the CORS that is not there, and what sits behind them.

`POST /api/audit` clones an arbitrary repository, runs Syft, Trivy and a local
model over it, writes to disk, and has no authentication. The bind address is
what stands between it and a machine on the network, so it is named in code for
the same reason `deps/syft_runner.py`'s `SYFT_ENV` is -- a setting a test can
read is a decision, while a command-line default is a habit -- and this file
reads it the way `test_offline_containment.py` reads that one.

**What is behind that one control grew.** The run history is durable now: every
repository URL anyone audited through this server, and the findings of every
finished run, in a file that outlives `artifacts/`. `docs/SCHEMAS.md` says
plainly that the endpoints have no authentication and that the history is
therefore readable by anything that can reach the port. The last test asserts
that -- an unauthenticated `GET /api/runs` is answered -- so the documented
weakness is a measured fact rather than a sentence, and cannot change to
something else without a test moving.

**CORS is asserted absent, and absent is a stronger claim than narrow.** This
wrapper used to be two origins: a Vite dev server on :5173 and the API on
:8000, joined by `CORSMiddleware` and an allow-list of two addresses, which
this file used to pin as a tuple. One server now serves the built page and the
API together, so the page fetches a relative path and there is no cross-origin
request left to permit. An allow-list of two is a policy that becomes `"*"` in
one edit and still looks deliberate; no middleware at all cannot be widened
without adding a middleware, which is a line of code a reviewer sees rather
than a string an editor changes.

What CORS never did is worth keeping straight, because the origin list looked
like the security control and was not: a cross-origin form POST still reaches
the handler, and only the *reply* is hidden from the page that sent it.
Loopback is the control, then and now.

Both readers below are run against a throwaway application that *does* install
CORS, because "no middleware carries an `allow_origins` kwarg" is exactly the
sentence an empty or mis-read stack satisfies for free.

This file skips when the server packages are not installed, and that costs
nothing it claims: with no fastapi and no uvicorn there is no server on this
machine to bind an address at all. The claim that no module under `src/`
imports those packages is a separate file,
`test_web_framework_containment.py`, and it never skips.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no server")
pytest.importorskip("uvicorn", reason="the web extra is not installed, so there is no server")

from fastapi import FastAPI                             # noqa: E402
from fastapi.middleware.cors import CORSMiddleware      # noqa: E402
from fastapi.testclient import TestClient               # noqa: E402

import api      # noqa: E402
import serve    # noqa: E402

# The only address this endpoint may listen on, and the wildcard it must not be.
LOOPBACK_HOST = "127.0.0.1"
ANY_INTERFACE = "0.0.0.0"  # named here to be forbidden, never bound

# The keyword a CORS policy is configured through, whichever middleware spells
# it. Read rather than the class alone, so a hand-rolled equivalent is caught.
ALLOWED_ORIGINS_KWARG = "allow_origins"

# The history endpoint, and the answer it gives with no credentials at all.
HISTORY_PATH = "/api/runs"
OK = 200

# The policy the probe application installs, to prove the readers below fire.
# It is the widest one there is, so a reader that missed it would be missing
# the worst case rather than an edge of one.
WILDCARD_ORIGIN = "*"


def configured_origin_lists(application: FastAPI) -> list:
    """Every allowed-origin list installed on an application's middleware stack."""
    return [middleware.kwargs[ALLOWED_ORIGINS_KWARG]
            for middleware in application.user_middleware
            if ALLOWED_ORIGINS_KWARG in middleware.kwargs]


def installed_middleware(application: FastAPI) -> list[type]:
    """The class of every middleware installed on an application."""
    return [middleware.cls for middleware in application.user_middleware]


def application_with_cors() -> FastAPI:
    """A throwaway application that does install CORS, for the mutation checks."""
    probe = FastAPI()
    probe.add_middleware(CORSMiddleware, allow_origins=[WILDCARD_ORIGIN])
    return probe


def test_the_server_binds_loopback() -> None:
    """The one decision `serve.py` exists to hold: the port is not published."""
    assert serve.BIND_HOST == LOOPBACK_HOST


def test_the_server_does_not_bind_every_interface() -> None:
    """Stated as its own refusal, so the mutation this guards against is named."""
    assert serve.BIND_HOST != ANY_INTERFACE


def test_no_middleware_configures_a_list_of_allowed_origins() -> None:
    """One origin serves both halves, so there is no policy to write and none is written."""
    assert configured_origin_lists(api.app) == []


def test_the_cors_middleware_is_not_in_the_stack() -> None:
    """The class itself, named: no policy at all, rather than a policy of two addresses."""
    assert CORSMiddleware not in installed_middleware(api.app)


def test_that_the_reader_would_notice_an_allowed_origin_list() -> None:
    """Mutation check: the empty list above is a fact about the app, not about the reader."""
    assert configured_origin_lists(application_with_cors()) == [[WILDCARD_ORIGIN]]


def test_that_the_reader_would_notice_the_cors_middleware() -> None:
    """Mutation check: the same for the class, so its absence above means it is absent."""
    assert CORSMiddleware in installed_middleware(application_with_cors())


def test_the_run_history_is_readable_with_no_credentials() -> None:
    """Documented, and asserted so it stays documented: loopback is the only control.

    Not a complaint about the design -- it is what `docs/SCHEMAS.md` and the
    README both say. The point of measuring it is that "no authentication" is
    the reason the bind address above matters, and a reader who sees this test
    knows the history is on the same footing as the audit endpoint.
    """
    response = TestClient(api.app).get(HISTORY_PATH)
    assert response.status_code == OK
    assert "runs" in response.json()
