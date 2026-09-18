"""A failed run names no directory and holds no envelope: what makes forgetting it safe.

`DELETE /api/runs/{run_id}` removes a **failed** row and nothing else, and its
docstring gives two reasons. This file is where both stop being prose.

**The first is a constraint, and it is checked here in the direction nothing
else checks.** `history_store`'s table carries
`CHECK ((status = 'finished') = (envelope IS NOT NULL))`, so a failed row's
envelope is NULL whatever any writer believes.
`test_history_rows.py` already holds the forward half -- a *finished* row with
no envelope is refused -- and the delete route leans on the reverse: a *failed*
row **with** one. Both halves come from the same `=`, but only one of them was
ever executed, and a constraint nobody has run in the direction they depend on
is a constraint they are trusting rather than using.

**The second is not a constraint but a property of the producers**, which is why
it needs a test at all. `artifacts_dir` is set in exactly one place --
`run_jobs.Registry._finish` -- so a run that never finished never names one.
Three paths reach `failed` and each is driven here rather than reasoned about:
a refusal the tool expects, an exception it does not, and `_reconcile`, which
flips a `running` row left behind by a stopped server.

**`_reconcile` is the one that is worth reading twice.** It copies
`artifacts_dir` across untouched -- it only writes `status`, `error` and
`finished_at` -- so the failed row it produces has no directory *because the
running row it started from had none*. That is a fact about the acceptance
record and the stage listener, both of which save from the record `Registry.start`
built, so the first test below asserts it at the source. A hand-planted running
row naming a directory would survive reconciliation still naming it; no producer
writes one, and this file measures the producers rather than the table.

None of this makes the route's check on `status` redundant, and the route keeps
it: these are the reasons the *narrowing* is safe, not a second place the
narrowing is enforced.

Free of fastapi throughout -- the registry, the record and the store all are --
so this runs on a checkout where the server packages were never installed. Every
store is under `tmp_path`, and `main.run` is replaced: no clone, no model, no
audit.
"""

import sqlite3

import pytest

from audit_request import AuditRequest
from history_store import open_store
from run_jobs import Registry
from run_record import FAILED, FINISHED, RUNNING

from .audit_stub import (
    AUDITOR, UNEXPECTED_ERROR, URL, artifacts_dir_for, open_a_store,
    stub_the_audit, wait_for_the_worker)
from .run_rows import WHEN, failed, running

# A refusal `main.EXPECTED_FAILURES` names, so the worker reports the tool's own
# sentence rather than a traceback.
EXPECTED_REFUSAL = ValueError("fetched/demo-app holds another repository")

# One the list does not name, so the broad catch is exercised too. Both land in
# `Registry._fail`, which is the method the route's argument is about.
UNEXPECTED_REFUSAL = UNEXPECTED_ERROR("something nobody planned for")

# The id of the row planted for the reconciliation test.
INTERRUPTED_ID = "a" * 32

# The columns a hand-written INSERT names, to get past `RunRecord` and meet the
# table's own constraints. `uploads` is NOT NULL, so it is here to keep the row
# from being refused for a reason other than the one under test.
RAW_COLUMNS = ("run_id, repo_url, auditor, options, started_at, status, "
               "finished_at, stages, error, uploads, envelope")


def a_registry(tmp_path):
    """A registry over a fresh store, which is all `api.py` builds."""
    return Registry(open_a_store(tmp_path))


def run_that_ends(registry, monkeypatch, tmp_path, error=None):
    """Start one audit, wait for the worker, and read back the record it stored."""
    stub_the_audit(monkeypatch, tmp_path, error=error)
    accepted = registry.start(AuditRequest(url=URL), AUDITOR)
    wait_for_the_worker(registry)
    stored = registry.store.get(accepted.run_id)
    assert stored is not None, "the registry accepted a run it did not store"
    return stored


def insert_raw(store, **values) -> None:
    """Write a row straight past `RunRecord`, to meet the table's own constraints."""
    named = RAW_COLUMNS.split(", ")
    marks = ",".join("?" for _ in named)
    with sqlite3.connect(store.path) as db:
        db.execute(f"INSERT INTO runs ({RAW_COLUMNS}) VALUES ({marks})",
                   [values.get(name) for name in named])


# --- the constraint the route's first argument rests on -------------------------

def test_a_failed_row_carrying_an_envelope_is_refused_by_the_table(tmp_path) -> None:
    """The reverse half of `(status = 'finished') = (envelope IS NOT NULL)`.

    This is the direction the delete route depends on and the one nothing else
    executes: a failed row cannot hold findings, so forgetting one destroys
    none. Refused by the database rather than by a writer's good intentions.
    """
    store = open_store(tmp_path / "runs", create=True)
    with pytest.raises(sqlite3.IntegrityError):
        insert_raw(store, run_id="b" * 32, repo_url=URL, auditor=AUDITOR,
                   options="{}", started_at=WHEN, status=FAILED, finished_at=WHEN,
                   stages="[]", error="refused", uploads="[]", envelope="{}")


def test_a_failed_row_with_no_envelope_is_accepted(tmp_path) -> None:
    """Non-vacuity: the refusal above is the envelope, not the rest of the row."""
    store = open_store(tmp_path / "runs", create=True)
    store.save(failed("b" * 32))
    assert store.get("b" * 32)[1] is None


# --- and the property its second argument rests on ------------------------------

def test_an_accepted_run_names_no_directory(monkeypatch, tmp_path) -> None:
    """Where the property starts: `Registry.start` builds a record with the column null."""
    stub_the_audit(monkeypatch, tmp_path)
    registry = a_registry(tmp_path)
    accepted = registry.start(AuditRequest(url=URL), AUDITOR)
    wait_for_the_worker(registry)
    assert accepted.artifacts_dir is None
    assert accepted.status == RUNNING


def test_a_run_that_failed_on_an_expected_refusal_names_no_directory(monkeypatch,
                                                                     tmp_path) -> None:
    """`Registry._fail` saves from the acceptance record, so the column stays null."""
    record, envelope = run_that_ends(a_registry(tmp_path), monkeypatch, tmp_path,
                                     error=EXPECTED_REFUSAL)
    assert record.status == FAILED
    assert (record.artifacts_dir, envelope) == (None, None)


def test_a_run_that_failed_unexpectedly_names_no_directory_either(monkeypatch,
                                                                  tmp_path) -> None:
    """The broad catch reaches the same `_fail`, so the second path is not a second rule."""
    record, envelope = run_that_ends(a_registry(tmp_path), monkeypatch, tmp_path,
                                     error=UNEXPECTED_REFUSAL)
    assert record.status == FAILED
    assert (record.artifacts_dir, envelope) == (None, None)


def test_a_run_interrupted_and_reconciled_names_no_directory(tmp_path) -> None:
    """The third path: a `running` row a stopped server left behind, failed on reopen.

    `_reconcile` writes `status`, `error` and `finished_at` and copies
    `artifacts_dir` across, so what makes this null is the running row it read
    -- which is the record `Registry.start` built.
    """
    store = open_store(tmp_path / "runs", create=True)
    store.save(running(INTERRUPTED_ID))
    reopened = open_store(tmp_path / "runs")
    record, envelope = reopened.get(INTERRUPTED_ID)
    assert record.status == FAILED
    assert (record.artifacts_dir, envelope) == (None, None)


# --- the one path that does name one --------------------------------------------

def test_a_finished_run_does_name_a_directory(monkeypatch, tmp_path) -> None:
    """Non-vacuity, and the whole reason the property is worth stating.

    Four nulls prove nothing if the column is never set at all. `_finish` is the
    one writer, which is what makes "failed implies null" a statement about the
    producers rather than about a field nobody uses.
    """
    record, envelope = run_that_ends(a_registry(tmp_path), monkeypatch, tmp_path)
    assert record.status == FINISHED
    assert record.artifacts_dir == str(artifacts_dir_for(tmp_path))
    assert envelope is not None
