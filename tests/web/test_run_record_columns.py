"""A record flattened into columns and read back, and the join against the real table.

`to_columns` and `from_columns` are serialisation, not SQL -- which is why they
live in `run_record.py` rather than in the store -- so they are tested apart
from the queries in `test_history_rows.py`. Three fields become JSON text on the
way: `stages`, whose order is its entire content; `options`, which must come
back *exactly* or a re-run is not the run that was asked for; and `uploads`,
which arrived in the same store version and is never null.

**One test here records the opposite of what it used to.** `options` carried
`auditor` and the sorted JSON therefore began `{"auditor"`, which this file
pinned deliberately as the duplication it was. The field came off `AuditRequest`
because replaying options that named a person would re-run the audit *as someone
else*, so the column now begins elsewhere and the name is asserted absent from
it -- while the `auditor` column beside it still carries one.

**The last three tests are the join that stops the store and the record
drifting.** `DURABLE_FIELDS` is derived from the dataclass and `history_store`'s
`_COLUMNS` from `DURABLE_FIELDS`, so those two cannot disagree by construction
-- but the SQL that creates the table is a hand-written string, and *that* is
what a field added to the record would leave behind. The column list is read
from a real database with `PRAGMA table_info` rather than from the module's own
constant, because the constant is the thing under suspicion.

No fastapi here: `run_record.py` and `history_store.py` are both free of it on
purpose, so this runs on a clean checkout with no web extra installed.
"""

import json
import sqlite3
from dataclasses import replace
from pathlib import Path

from history_store import ENVELOPE, open_store
from run_record import (
    COMPUTED_FIELDS, DURABLE_FIELDS, REPLY_SCHEMA_VERSION, RunRecord,
    from_columns, to_columns)

URL = "https://example.invalid/owner/demo-app"
AUDITOR = "Quokka Reviewer"

# Exactly `AuditRequest`'s fields, which is what the column holds. No `auditor`:
# it is a field of the record, not an option of the audit.
OPTIONS = {"url": URL, "model": "", "semantic_probe": True, "draft_key": False,
           "compare_models": False, "cloud_model": ""}

# Two announced stages, in order, because the order is the whole content.
STAGES = ["fetch", "surfaces"]

# One attached file, as the upload route records one. Here because `uploads` is
# the third JSON column and landed in the same store version as `auditor`.
UPLOADS = [{"upload_id": "b" * 32, "name": "evidence.txt", "bytes": 12,
            "sha256": "c" * 64}]

WHEN = "2026-09-09T12:00:00+00:00"
SECONDS = 1.5

# A stored envelope, cut down to the one key a round trip has to preserve.
ENVELOPE_TEXT = {"schema_version": REPLY_SCHEMA_VERSION, "app": "demo-app"}

RUN_ID_LENGTH = 32

# Where `auditor` sits: third, straight after the two facts known at acceptance
# that came before it. It is required, so it carries no default and cannot
# follow the defaulted fields -- which is what reordered the stored columns.
AUDITOR_COLUMN_INDEX = 2


def a_finished_record() -> RunRecord:
    """One run that got all the way through, with every nullable field set."""
    accepted = RunRecord(run_id="a" * RUN_ID_LENGTH, repo_url=URL, auditor=AUDITOR,
                         options=dict(OPTIONS), started_at=WHEN)
    return replace(accepted, status="finished", finished_at=WHEN, seconds=SECONDS,
                   stages=list(STAGES), app="demo-app",
                   artifacts_dir="artifacts/agentic_auditor/demo-app",
                   finding_count=3, surface_count=6, uploads=list(UPLOADS))


def stored_columns(tmp_path: Path) -> list[str]:
    """The table's real columns, read off a database rather than off a constant."""
    store = open_store(tmp_path / "runs", create=True)
    with sqlite3.connect(store.path) as db:
        return [row[1] for row in db.execute("PRAGMA table_info(runs)")]


def test_a_record_survives_the_trip_to_columns_and_back() -> None:
    """Every field, including the two that become JSON text on the way."""
    record = a_finished_record()
    returned, envelope = from_columns(to_columns(record, None))
    assert returned == record
    assert envelope is None


def test_the_three_structured_fields_come_back_as_the_structures_they_were() -> None:
    """The JSON columns, named: `stages` order is its content and `options` must be exact."""
    returned, _ = from_columns(to_columns(a_finished_record(), None))
    assert returned.options == OPTIONS
    assert returned.stages == STAGES
    assert returned.uploads == UPLOADS


def test_the_structured_fields_are_stored_as_sorted_json_text() -> None:
    """Written with `sort_keys`, so the stored text does not vary between equal records."""
    columns = to_columns(a_finished_record(), None)
    assert columns["stages"] == '["fetch", "surfaces"]'
    assert columns["options"] == json.dumps(OPTIONS, sort_keys=True)


def test_a_run_with_no_attachments_stores_an_empty_list_and_not_null() -> None:
    """`[]` is a fact the endpoint can always establish, which is why the column is NOT NULL."""
    accepted = replace(a_finished_record(), uploads=[])
    assert to_columns(accepted, None)["uploads"] == "[]"
    assert from_columns(to_columns(accepted, None))[0].uploads == []


def test_the_options_column_names_nobody_and_the_auditor_column_does() -> None:
    """The two used to be one answer written twice, and they had already disagreed.

    The record stored the stripped name and `options["auditor"]` kept the
    padding the browser sent. One of them had to go, and it was the one a re-run
    replays.
    """
    columns = to_columns(a_finished_record(), None)
    assert AUDITOR not in columns["options"]
    assert "auditor" not in json.loads(columns["options"])
    assert columns["auditor"] == AUDITOR


def test_an_envelope_travels_beside_the_record_rather_than_inside_it() -> None:
    """`from_columns` hands back a pair: the record's fields, then what it stored."""
    returned, envelope = from_columns(to_columns(a_finished_record(), ENVELOPE_TEXT))
    assert envelope == ENVELOPE_TEXT
    assert not hasattr(returned, ENVELOPE)


# --- the join that stops the store and the record drifting --------------------

def test_the_tables_columns_are_the_records_fields_plus_the_envelope(tmp_path) -> None:
    """A field added to the record and not to the hand-written SQL is caught here."""
    assert stored_columns(tmp_path) == [*DURABLE_FIELDS, ENVELOPE]


def test_the_computed_flags_are_not_columns(tmp_path) -> None:
    """A stored flag about the filesystem becomes a lie the moment `artifacts/` is cleaned."""
    assert set(COMPUTED_FIELDS).isdisjoint(stored_columns(tmp_path))


def test_the_column_list_really_was_read_off_a_database(tmp_path) -> None:
    """Guard: an empty pragma result would make the join above compare against nothing."""
    assert len(stored_columns(tmp_path)) == len(DURABLE_FIELDS) + 1
    assert "run_id" in stored_columns(tmp_path)


def test_the_required_fields_come_before_every_defaulted_one(tmp_path) -> None:
    """Why the columns moved: `auditor` is required, so it cannot follow a defaulted field.

    The order is the dataclass's and the dataclass's order is the table's, so a
    required field added at the end is a `TypeError` at import rather than a
    choice anybody made. Asserted against the real table, not the constant.
    """
    columns = stored_columns(tmp_path)
    assert columns[:AUDITOR_COLUMN_INDEX + 1] == ["run_id", "repo_url", "auditor"]
