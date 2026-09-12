"""One audit at a time, and the slot released on every way out of `Registry.start`.

`web/run_jobs.py` runs one audit at a time because two would race between the
"already fetched?" check and the clone, and would overwrite each other's
`artifacts/<app>/` mid-write. That is driven here through the registry rather
than by racing two real audits: a test that has to win a race to fail is a test
that passes on a slow machine and proves nothing. The run in flight is held open
by an `Event` the test sets, so "in flight" is a fact rather than a timing hope.

**The unwritable-store tests are a regression.** `start` claimed the slot and
then did work that can raise -- the first store write, the thread launch --
before the worker's `finally` existed to release it. A store that could not be
written therefore wedged every later request at 409 until the server was
restarted. It releases the slot and re-raises now, and the two tests at the
bottom assert both halves: the slot is free afterwards, and the next request
is answered rather than refused as a second run.

Mutual exclusion moved here from a module-level lock in `api.py`, so this is
also where the 409's own condition lives; `test_api_single_run_lock.py` asserts
what the endpoint answers when it is true. Nothing here needs fastapi.
"""

import pytest

from audit_request import AuditRequest
from history_store import HistoryStore
from run_jobs import Busy, Registry
from run_record import FINISHED, RunRecord

from .audit_stub import (
    URL, UNEXPECTED_ERROR, hold_the_audit, open_a_store, stub_the_audit,
    wait_for_the_worker)

# The sentence a refusal carries. `ValueError` is one of `main.EXPECTED_FAILURES`,
# so this is a run that failed the way a user can fix rather than a defect.
TOOL_MESSAGE = "fetched/demo-app holds another repository; remove it to fetch this one"


class SaveRefused(RuntimeError):
    """What a store that cannot be written raises, in this file and nowhere else."""


class StoreThatFailsOnce:
    """A store double whose first write raises and whose later writes behave."""

    def __init__(self, real: HistoryStore) -> None:
        """Hold the real store every write after the first is delegated to."""
        self.real = real
        self.refusals_left = 1

    def save(self, record: RunRecord, envelope: dict | None = None) -> None:
        """Refuse the first write, exactly as an unwritable database would."""
        if self.refusals_left:
            self.refusals_left -= 1
            raise SaveRefused("the run history could not be written")
        self.real.save(record, envelope)

    def get(self, run_id: str) -> tuple[RunRecord, dict | None] | None:
        """Read through to the real store, so a stored run is still readable."""
        return self.real.get(run_id)


def a_request() -> AuditRequest:
    """One audit the page asked for."""
    return AuditRequest(url=URL)


def run_to_completion(registry: Registry) -> tuple[RunRecord, dict | None]:
    """Start one audit, wait for the worker, and read back what it stored."""
    accepted = registry.start(a_request())
    wait_for_the_worker(registry)
    stored = registry.store.get(accepted.run_id)
    assert stored is not None, "the registry accepted a run it did not store"
    return stored


def test_a_second_audit_while_one_is_in_flight_is_refused(monkeypatch, tmp_path) -> None:
    """One at a time: two would race over the same fetch and the same artifacts directory."""
    let_it_finish = hold_the_audit(monkeypatch, tmp_path)
    registry = Registry(open_a_store(tmp_path))
    registry.start(a_request())
    try:
        with pytest.raises(Busy, match="already running"):
            registry.start(a_request())
    finally:
        let_it_finish.set()
    wait_for_the_worker(registry)


def test_the_slot_is_free_after_a_finished_run(monkeypatch, tmp_path) -> None:
    """The wrapper is single-file, not single-use: two audits in a row both run."""
    stub_the_audit(monkeypatch, tmp_path)
    registry = Registry(open_a_store(tmp_path))
    run_to_completion(registry)
    assert registry.active_run_id() is None
    run_to_completion(registry)
    assert registry.store.count() == 2


def test_the_slot_is_free_after_a_refused_run(monkeypatch, tmp_path) -> None:
    """A failed run must not wedge the server shut, which is what the `finally` is for."""
    stub_the_audit(monkeypatch, tmp_path, error=ValueError(TOOL_MESSAGE))
    registry = Registry(open_a_store(tmp_path))
    run_to_completion(registry)
    assert registry.active_run_id() is None


def test_the_slot_is_free_after_an_unexpected_failure(monkeypatch, tmp_path) -> None:
    """The path a refusal cannot cover: a defect unwinds through the worker instead."""
    stub_the_audit(monkeypatch, tmp_path, error=UNEXPECTED_ERROR("a bug, not a refusal"))
    registry = Registry(open_a_store(tmp_path))
    run_to_completion(registry)
    assert registry.active_run_id() is None


# --- the store that could not be written --------------------------------------

def test_a_store_that_refuses_the_first_write_does_not_wedge_the_slot(monkeypatch,
                                                                      tmp_path) -> None:
    """The regression: `start` claimed the slot before the worker's `finally` existed."""
    stub_the_audit(monkeypatch, tmp_path)
    registry = Registry(StoreThatFailsOnce(open_a_store(tmp_path)))
    with pytest.raises(SaveRefused):
        registry.start(a_request())
    assert registry.active_run_id() is None


def test_the_request_after_an_unwritable_store_is_not_refused_as_busy(monkeypatch,
                                                                      tmp_path) -> None:
    """Said as the user meets it: the next request runs, rather than answering 409 for ever."""
    stub_the_audit(monkeypatch, tmp_path)
    registry = Registry(StoreThatFailsOnce(open_a_store(tmp_path)))
    with pytest.raises(SaveRefused):
        registry.start(a_request())
    record, _ = run_to_completion(registry)
    assert record.status == FINISHED
