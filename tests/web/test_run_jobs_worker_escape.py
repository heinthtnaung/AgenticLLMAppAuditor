"""A worker whose audit never starts, and the row it must still leave behind.

**The assertion with teeth is the record's status, not a 400.** A request naming
a model called `-x` made `parse_args` print usage and call `sys.exit` inside the
worker thread. `SystemExit` is a `BaseException`, so it escaped both of
`_work`'s catches: the thread died, the `finally` freed the slot, and the run
row said `running` for ever. `history_store._reconcile` only runs when the store
is opened, so the row survived every later request until the server restarted.

The request is refused before it reaches here now -- that rule is
`test_audit_request_option_values.py`. **This file is the second fix**, which is
`except BaseException` in `_work`, and it is defence in depth for the *next*
escape rather than for this one. So the registry is driven directly, with an
`AuditRequest` built by hand, which is the layer below the rule: what must be
true is that **no argv reaching the worker can leave a run un-terminal**.

Put `except Exception` back and every test in the first section fails on the
status, having waited for the slot the `finally` still releases.

No fastapi, like `test_run_jobs.py` beside it: `web/run_jobs.py` is free of it,
and the engine is testable on a clean checkout. `main.run` is replaced
throughout, so nothing here clones, calls a model or audits anything --
`parse_args` fails first, which the recorder proves.
"""

from pathlib import Path

import pytest

import main
import run_jobs
from audit_request import AuditRequest
from run_jobs import Registry
from run_record import FAILED, FINISHED, RUNNING, RunRecord

from .audit_stub import (
    AUDITOR, TERMINAL_STATUSES, URL, open_a_store, repositories, stub_the_audit,
    wait_for_the_worker)

# The value that wedged a row: `--model -x` makes argparse print usage and exit.
# Kept beside an option that would really consult a model, so the command line
# it builds is the one a legal-looking request builds.
OPTION_SHAPED_MODEL = "-x"

# What the parser raises, named because the stored error has to carry it: a row
# saying only "failed" tells nobody a command line was malformed.
ESCAPING_CLASS = SystemExit


def a_registry(tmp_path: Path) -> Registry:
    """A registry over a fresh store under `tmp_path`, which is all `api.py` builds."""
    return Registry(open_a_store(tmp_path))


def an_option_shaped_request() -> AuditRequest:
    """One audit whose argv `main.build_parser` will not parse.

    Built directly rather than posted: `AuditRequest.refusals` stops this at the
    route, and what is under test is the layer that runs after a request was
    accepted.
    """
    return AuditRequest(url=URL, model=OPTION_SHAPED_MODEL, semantic_probe=True)


def run_to_completion(registry: Registry, asked: AuditRequest) -> RunRecord:
    """Start one audit, wait for the worker to let the slot go, and read the row back."""
    accepted = registry.start(asked, AUDITOR)
    wait_for_the_worker(registry)
    stored = registry.store.get(accepted.run_id)
    assert stored is not None, "the registry accepted a run it did not store"
    record, _envelope = stored
    return record


# --- the row a dead worker used to leave ----------------------------------------

def test_a_command_line_the_parser_refuses_leaves_a_terminal_run(monkeypatch,
                                                                 tmp_path) -> None:
    """The fault itself: `running` for ever was the measured outcome, on any status but this."""
    stub_the_audit(monkeypatch, tmp_path)
    record = run_to_completion(a_registry(tmp_path), an_option_shaped_request())
    assert record.status in TERMINAL_STATUSES, record.status


def test_that_run_is_failed_and_not_still_running(monkeypatch, tmp_path) -> None:
    """Said as both halves, because `running` is the one answer a poll can never resolve."""
    stub_the_audit(monkeypatch, tmp_path)
    record = run_to_completion(a_registry(tmp_path), an_option_shaped_request())
    assert record.status == FAILED
    assert record.status != RUNNING


def test_the_stored_error_names_the_class_that_escaped(monkeypatch, tmp_path) -> None:
    """A row saying only "failed" sends a reader to the server's stderr; this one names it."""
    stub_the_audit(monkeypatch, tmp_path)
    record = run_to_completion(a_registry(tmp_path), an_option_shaped_request())
    assert ESCAPING_CLASS.__name__ in record.error


def test_the_audit_itself_was_never_reached(monkeypatch, tmp_path) -> None:
    """Non-vacuity, and the safety claim: the parse fails first, so nothing was audited."""
    parsed = stub_the_audit(monkeypatch, tmp_path)
    run_to_completion(a_registry(tmp_path), an_option_shaped_request())
    assert repositories(parsed) == []


def test_the_slot_is_free_afterwards(monkeypatch, tmp_path) -> None:
    """The half that always worked: the `finally` releases it, which is why the row survived."""
    stub_the_audit(monkeypatch, tmp_path)
    registry = a_registry(tmp_path)
    run_to_completion(registry, an_option_shaped_request())
    assert registry.active_run_id() is None


# --- why neither existing catch held it ------------------------------------------

def test_the_escaping_class_is_not_one_the_refusals_would_have_caught() -> None:
    """`REFUSALS` is the tool's own list of things a person can fix, and this is not one."""
    assert not any(issubclass(ESCAPING_CLASS, held) for held in run_jobs.REFUSALS)


def test_the_escaping_class_is_not_an_exception_at_all() -> None:
    """Which is why the broad catch is `BaseException`: `except Exception` misses this."""
    assert not issubclass(ESCAPING_CLASS, Exception)


def test_the_parser_really_is_what_raises_it() -> None:
    """The seam named, so the tests above are about argparse and not about the stub."""
    with pytest.raises(ESCAPING_CLASS):
        main.build_parser().parse_args(an_option_shaped_request().to_argv())


# --- the off position ------------------------------------------------------------

def test_a_request_the_parser_accepts_still_finishes(monkeypatch, tmp_path) -> None:
    """Without it, a worker that failed every run would pass every test above."""
    parsed = stub_the_audit(monkeypatch, tmp_path)
    record = run_to_completion(a_registry(tmp_path),
                               AuditRequest(url=URL, semantic_probe=True))
    assert record.status == FINISHED, record.error
    assert repositories(parsed) == [URL]
