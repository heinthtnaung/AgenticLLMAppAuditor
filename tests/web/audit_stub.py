"""The replaced audit and the wait for the worker thread. No server, no model, no clone.

Split from `api_stubs.py` for the reason `web/run_jobs.py` and
`web/run_record.py` are themselves free of fastapi: the job engine -- the single
slot, the stages, the terminal status -- is testable on a clean checkout where
the server packages were never installed, and `test_run_jobs.py` drives the
registry directly to prove it. `api_stubs.py` imports this and adds the HTTP
half, so there is still one spelling of the replaced audit rather than two.

`main.run` takes a stage listener now, so the fake takes one too and announces
through it. That signature is the whole reason this file exists as code rather
than as three lines copied into six tests: a stub with the old arity fails
inside a worker thread, where the traceback goes to stderr and the run comes
back as `failed` with a `TypeError` -- readable, but not as a test failure.

Every store opened here is under `tmp_path`, never the checkout's own.
"""

import argparse
import threading
import time
from pathlib import Path

import pytest

import history_store
import main
from run_jobs import Registry

URL = "https://example.invalid/owner/demo-app"

# What a stubbed audit says it produced, in the shape `audit_run.audit` returns
# and `web/run_jobs.py` subscripts. `artifacts` is under tmp_path, so a test
# that read it back would read its own tree and never the repository's.
APP = "demo-app"
RUN_SECONDS = 0.5

# An error class deliberately absent from `main.EXPECTED_FAILURES`, so a test
# can tell a translated refusal from a blanket `except Exception`.
UNEXPECTED_ERROR = KeyError

# The statuses a run stops at. `running` is not one of them, which is what every
# wait below is waiting to stop seeing.
TERMINAL_STATUSES = ("finished", "failed")

# How long a stubbed audit may take before a wait gives up and says so. The fake
# returns immediately, so this is a hang detector and not a timing assumption --
# a machine slow enough to need more than this has something else wrong with it.
WORKER_TIMEOUT_SECONDS = 10.0
POLL_SECONDS = 0.005


def open_a_store(tmp_path: Path) -> history_store.HistoryStore:
    """A run history in a directory this test owns, created on the spot."""
    return history_store.open_store(tmp_path / "runs", create=True)


def artifacts_dir_for(tmp_path: Path) -> Path:
    """Where the stubbed audit will say it wrote, so a test can plant documents there."""
    return tmp_path / "artifacts" / APP


def _produced(tmp_path: Path) -> dict:
    """What a stubbed audit answers with, in the shape `audit_run.audit` returns."""
    return {"app": APP, "artifacts": artifacts_dir_for(tmp_path),
            "seconds": RUN_SECONDS, "advisories_read": False}


def stub_the_audit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                   error: Exception | None = None,
                   announces: tuple[str, ...] = ()) -> list[argparse.Namespace]:
    """Replace the audit with a recorder that announces, then answers or raises.

    Returns the command lines the wrapper built, so a test can assert the run
    was really asked for what the request said -- a stub that ran an ordinary
    audit would satisfy every status check while a checkbox did nothing.
    """
    parsed: list[argparse.Namespace] = []

    def fake_run(args: argparse.Namespace, on_stage=None) -> dict:
        """Record the command line, announce the named stages, then answer or refuse."""
        parsed.append(args)
        for name in announces:
            on_stage(name, "")
        if error is not None:
            raise error
        return _produced(tmp_path)

    monkeypatch.setattr(main, "run", fake_run)
    return parsed


def hold_the_audit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> threading.Event:
    """Replace the audit with one that waits, and return the event that lets it finish.

    How a test gets a run that is genuinely in flight: a test that has to win a
    race to fail is a test that passes on a slow machine and proves nothing.
    Always set the event, in a `finally`, or the worker holds the slot until the
    timeout.
    """
    let_it_finish = threading.Event()

    def fake_run(args: argparse.Namespace, on_stage=None) -> dict:
        """Hold the run open until the test says otherwise, then answer normally."""
        assert let_it_finish.wait(timeout=WORKER_TIMEOUT_SECONDS), (
            "the test never released the held audit")
        return _produced(tmp_path)

    monkeypatch.setattr(main, "run", fake_run)
    return let_it_finish


def repositories(parsed: list[argparse.Namespace]) -> list[str]:
    """Every repository the recorded command lines named, in order."""
    return [args.repo_path for args in parsed]


def wait_for_the_worker(registry: Registry) -> None:
    """Block until the registry's single-run slot is free again.

    The worker releases it in a `finally` that runs after the terminal row is
    stored, so a run seen as released is a run already written -- there is no
    half-finished moment for a test to read.
    """
    deadline = time.monotonic() + WORKER_TIMEOUT_SECONDS
    while registry.active_run_id() is not None:
        assert time.monotonic() < deadline, (
            f"the slot was still held by {registry.active_run_id()} after "
            f"{WORKER_TIMEOUT_SECONDS} seconds; the worker never released it")
        time.sleep(POLL_SECONDS)
