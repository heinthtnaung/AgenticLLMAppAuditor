"""Rows in the run history: what goes in, what comes back, and what the table refuses.

`save` and `get`, over databases built under `tmp_path`. One subject worth
naming apart from the round trip:

**The `CHECK` constraints are asserted with raw SQL**, because `RunRecord`
already refuses the same three combinations and a record cannot be used to test
the second line of defence. The point of having both is that a writer which
bypassed the dataclass -- a migration, a fixture, a future endpoint -- still
cannot store a row that is not true, so the test has to bypass it too.

`superseded`, the newest-first list and the count are the three queries a
reader rather than a writer asks, and they are `test_history_queries.py`.

Nothing here skips -- `history_store.py` is free of fastapi -- and nothing here
touches the checkout's own `runs/history.sqlite3`.
"""

import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from history_store import HistoryStore, open_store
from run_record import RunRecord

URL = "https://example.invalid/owner/demo-app"
# Who asked for the run. Required since the wire version went to 3, so every
# record built here carries one.
AUDITOR = "Quokka Reviewer"
OPTIONS = {"url": URL, "semantic_probe": False}
ARTIFACTS = "artifacts/agentic_auditor/demo-app"
# One timestamp, at the precision `run_record.now()` writes: seconds.
LATE = "2026-09-09T12:00:00+00:00"

ENVELOPE = {"schema_version": 2, "app": "demo-app"}

# One attached file, as `web/uploads.py` records one. Stored with the run rather
# than in a table of its own, which is why it is a column here at all.
ATTACHMENT = {"upload_id": "e" * 32, "name": "evidence.txt", "bytes": 12,
              "sha256": "f" * 64}

# The columns a hand-written INSERT names, when the point is to get past
# `RunRecord` and meet the table's own constraints. `uploads` is among them
# because the column is NOT NULL: `[]` is a fact the endpoint can always
# establish -- nothing was attached -- and never a gap, so a row that omitted it
# would be refused for that rather than for the constraint under test.
_RAW_COLUMNS = ("run_id, repo_url, auditor, options, started_at, status, "
                "finished_at, stages, error, uploads, envelope")


def a_store(tmp_path: Path) -> HistoryStore:
    """An empty run history in a directory this test owns."""
    return open_store(tmp_path / "runs", create=True)


def running(run_id: str, started_at: str = LATE) -> RunRecord:
    """One accepted run."""
    return RunRecord(run_id=run_id, repo_url=URL, auditor=AUDITOR,
                     options=dict(OPTIONS), started_at=started_at)


def finished(run_id: str, started_at: str = LATE,
             artifacts_dir: str = ARTIFACTS) -> RunRecord:
    """One run that got all the way through, with a directory to be superseded in."""
    return replace(running(run_id, started_at), status="finished", finished_at=LATE,
                   seconds=2.0, stages=["fetch", "write"], app="demo-app",
                   artifacts_dir=artifacts_dir, finding_count=4, surface_count=7)


def insert_raw(store: HistoryStore, **values) -> None:
    """Write a row straight past `RunRecord`, to meet the table's own constraints."""
    named = _RAW_COLUMNS.split(", ")
    marks = ",".join("?" for _ in named)
    with sqlite3.connect(store.path) as db:
        db.execute(f"INSERT INTO runs ({_RAW_COLUMNS}) VALUES ({marks})",
                   [values.get(name) for name in named])


def raw_values(**changed) -> dict:
    """A row that satisfies every constraint, so one field at a time can break it."""
    return {"run_id": "c" * 32, "repo_url": URL, "auditor": AUDITOR,
            "options": "{}", "started_at": LATE, "status": "running",
            "finished_at": None, "stages": "[]", "error": None,
            "uploads": "[]", "envelope": None, **changed}


# --- one row in, one row out ---------------------------------------------------

def test_a_saved_run_comes_back_as_the_record_it_was(tmp_path) -> None:
    """The round trip through SQLite, asserted on the whole record and not on one field."""
    store = a_store(tmp_path)
    record = finished("a" * 32)
    store.save(record, ENVELOPE)
    assert store.get(record.run_id) == (record, ENVELOPE)


def test_a_run_nobody_stored_reads_as_nothing_rather_than_raising(tmp_path) -> None:
    """`None` is what the route turns into its 404, so a miss must be a miss."""
    assert a_store(tmp_path).get("d" * 32) is None


def test_saving_the_same_run_twice_replaces_it_rather_than_adding_a_row(tmp_path) -> None:
    """A run is saved at every stage, so `INSERT OR REPLACE` is the whole mechanism."""
    store = a_store(tmp_path)
    accepted = running("a" * 32)
    store.save(accepted)
    store.save(replace(accepted, stages=["fetch"]))
    assert store.count() == 1
    assert store.get(accepted.run_id)[0].stages == ["fetch"]


def test_an_envelope_is_stored_and_returned_as_content_not_as_bytes(tmp_path) -> None:
    """Byte-identity with the artifact files is not claimed; equality after parsing is."""
    store = a_store(tmp_path)
    store.save(finished("a" * 32), ENVELOPE)
    assert store.get("a" * 32)[1] == ENVELOPE


# --- what the table refuses ----------------------------------------------------

def test_a_finished_row_with_no_envelope_is_refused_by_the_table(tmp_path) -> None:
    """`status == finished` iff `result`: a finished run whose findings are gone is not one."""
    store = a_store(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        insert_raw(store, **raw_values(status="finished", finished_at=LATE))


def test_a_failed_row_with_no_error_is_refused_by_the_table(tmp_path) -> None:
    """`status == failed` iff `error`: a failure with nothing to show is a blank in the UI."""
    store = a_store(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        insert_raw(store, **raw_values(status="failed", finished_at=LATE))


def test_a_running_row_with_a_finish_time_is_refused_by_the_table(tmp_path) -> None:
    """`running` iff `finished_at is null`, enforced here as well as in the dataclass."""
    store = a_store(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        insert_raw(store, **raw_values(status="running", finished_at=LATE))


def test_a_status_outside_the_vocabulary_is_refused_by_the_table(tmp_path) -> None:
    """The closed set is a constraint too, built from `RUN_STATUSES` itself."""
    store = a_store(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        insert_raw(store, **raw_values(status="cancelled", finished_at=LATE))


def test_a_row_with_no_attachment_list_at_all_is_refused_by_the_table(tmp_path) -> None:
    """`uploads` is NOT NULL: nothing attached is `[]`, which is a fact and not a gap.

    The distinction every nullable column here exists for, applied in reverse.
    `finding_count` is null when no document stands behind it; an attachment
    list always has a document behind it, because the endpoint is the only thing
    that can add one.
    """
    store = a_store(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        insert_raw(store, **raw_values(uploads=None))


def test_a_row_that_breaks_nothing_is_accepted(tmp_path) -> None:
    """Non-vacuity: the refusals above are about the constraints, not about the INSERT."""
    store = a_store(tmp_path)
    insert_raw(store, **raw_values())
    assert store.count() == 1


def test_an_attached_file_survives_the_round_trip(tmp_path) -> None:
    """The third JSON column, stored and read back: the upload route saves the whole record."""
    store = a_store(tmp_path)
    attached = replace(finished("a" * 32), uploads=[ATTACHMENT])
    store.save(attached, ENVELOPE)
    assert store.get(attached.run_id)[0].uploads == [ATTACHMENT]
