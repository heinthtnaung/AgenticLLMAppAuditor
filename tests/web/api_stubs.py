"""One application over a throwaway store, and the poll a page has to do now.

Every file here that drives an endpoint needs the same application over the same
kind of store -- what an outcome becomes, what the lock does, what the record
carries, what the routes answer, what a download serves -- so it is spelled once
here and they cannot drift. The replaced audit itself is
`audit_stub.py`, which is free of fastapi so `test_run_jobs.py` can use it on a
clean checkout.

**Every application built here is a fresh one over a store under `tmp_path`, not
`api.app`.** `web/api.py` opens the real history at import and hands it to
`downloads.register` as a closure argument, so a later `api.STORE = ...` would
redirect the run routes -- they read `registry.store` on every call -- and leave
the downloads pointed at the checkout's own database. Assembling the two routers
the way `api.py` assembles them costs three lines, isolates every test's rows
from every other's, and is the only form that redirects both halves.
`tests/web/__init__.py` keeps the *import* off the real file; this keeps the rows
off it.

**The audit is a background thread now, so a test has to wait.** `POST
/api/audit` answers 202 before there is anything to see, exactly as the page
sees it, and `poll_until_terminal` polls `GET /api/runs/{id}` the way the page
polls, under a deadline. The tests whose subject is the slot rather than the
record wait on `audit_stub.wait_for_the_worker` instead.

Nothing here calls `pytest.importorskip`. It imports fastapi outright, and httpx
for the response type; every test module that imports it skips on the web extra
before it reaches this import.
"""

import time
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

import downloads
import history_store
import run_routes
from run_jobs import Registry

from .audit_stub import (
    AUDITOR, POLL_SECONDS, TERMINAL_STATUSES, URL, WORKER_TIMEOUT_SECONDS,
    open_a_store)

ENDPOINT = "/api/audit"
RUNS = "/api/runs"

OK = 200
ACCEPTED = 202


def application_over(store: history_store.HistoryStore) -> tuple[FastAPI, Registry]:
    """The API's two routers over one store, assembled the way `api.py` assembles them."""
    app = FastAPI()
    registry = Registry(store)
    run_routes.register(app, registry)
    downloads.register(app, store)
    return app, registry


def client_over(tmp_path: Path) -> tuple[TestClient, Registry]:
    """A client on a fresh application whose history is under `tmp_path`."""
    app, registry = application_over(open_a_store(tmp_path))
    return TestClient(app), registry


def post_an_audit(client: TestClient, url: str = URL, **options) -> httpx.Response:
    """Post one audit request and return the response, whatever its status.

    The body carries an `auditor` because the request rules now require one: a
    post without it is a 400 before any row is written, which would make every
    test through this helper a test of that refusal. `**options` still wins, so
    a test whose subject *is* the name passes its own -- including a blank one.
    """
    return client.post(ENDPOINT, json={"url": url, "auditor": AUDITOR, **options})


def accepted_run_id(client: TestClient, url: str = URL, **options) -> str:
    """Post one audit, insist it was accepted, and return the run id it answered with."""
    response = post_an_audit(client, url, **options)
    assert response.status_code == ACCEPTED, response.text
    return response.json()["run_id"]


def read_run(client: TestClient, run_id: str) -> dict:
    """One run record, read the way the page reads it."""
    response = client.get(f"{RUNS}/{run_id}")
    assert response.status_code == OK, response.text
    return response.json()


def poll_until_terminal(client: TestClient, run_id: str) -> dict:
    """Poll the run as the page does, until it stops saying `running`."""
    deadline = time.monotonic() + WORKER_TIMEOUT_SECONDS
    while True:
        record = read_run(client, run_id)
        if record["status"] in TERMINAL_STATUSES:
            return record
        assert time.monotonic() < deadline, (
            f"run {run_id} was still {record['status']} after {WORKER_TIMEOUT_SECONDS} "
            "seconds; the worker never reached a terminal status")
        time.sleep(POLL_SECONDS)


def audit_and_poll(client: TestClient, url: str = URL, **options) -> dict:
    """Post one audit and answer with its terminal record, which is what a page ends up with."""
    return poll_until_terminal(client, accepted_run_id(client, url, **options))
