"""Past runs, in SQLite. The first durable state this project owns.

Worth saying what it is not: not JSON, not byte-identical, not produced by
`src/`, and not read by any phase. `src/` does not know it exists, so an audit
run from a terminal writes no row -- the command line's behaviour is unchanged.

**It refuses rather than migrates.** A file at another version is named and left
alone, exactly as a scorer refuses a grading key whose vocabulary has moved
under it. And it never connects to a path it has not decided about first,
because `sqlite3.connect` *creates* the file -- the same trap
`src/retrieval/store.py` closes for ChromaDB, whose client writes a database on
a missing path.
"""

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from run_record import (
    DURABLE_FIELDS, ENVELOPE, FAILED, INTERRUPTED, MODEL_FIELDS, RUNNING,
    RUN_STATUSES, RunRecord, from_columns, now, to_columns)

# The file's own version, unrelated to the wire's: one versions a file, the
# other versions a protocol. Held in `PRAGMA user_version` rather than a table
# because a table must be *found* before it can be read, so `SELECT ... FROM
# meta` raises on exactly the files whose schema you are trying to detect.
# The pragma answers 0 for any SQLite file ever written, which makes "0 means
# not ours, or not initialised" a total answer instead of an exception.
STORE_SCHEMA_VERSION = 2

# Anchored to the repository, the way `page.py` anchors the built page -- not
# relative to the working directory. `api.py` opens the store when it is
# imported and `serve.py` chdirs to the repo root *after* that import returns,
# so a relative default put the history wherever the server happened to be
# started: a run history that forgets, in an untracked directory, holding every
# repository URL anyone audited.
#
# Not under `artifacts/`: everything there is a documented artifact with a
# schema and a byte-identical guarantee, and a mutable database would be a new
# kind of object in a directory a reader has already learned.
STORE_DIR = Path(__file__).resolve().parents[1] / "runs"
STORE_NAME = "history.sqlite3"

# Newest first, and capped: the list is a view, not an export.
HISTORY_LIST_LIMIT = 50

# The record's own fields, plus the one column that is not a field of it.
_COLUMNS = (*DURABLE_FIELDS, ENVELOPE)

# Where each arm recorded the model that answered, inside the envelope. Keyed by
# `run_record.MODEL_FIELDS` so the query is built in that tuple's order and the
# two cannot drift; interpolated into SQL from these constants and never from a
# request, which is the rule `_created` states for its own PRAGMA.
#
# A second spelling of a shape `run_jobs._arm` also builds, in Python. That pair
# already exists for `$.comparison.artifacts_dir`, and it is noted here rather
# than left to be discovered.
_MODEL_PATHS = {
    "local_model_identifier": "$.findings.model_run.model_identifier",
    "local_model_status": "$.findings.model_run.status",
    "cloud_model_identifier": "$.comparison.findings.model_run.model_identifier",
    "cloud_model_status": "$.comparison.findings.model_run.status",
}
assert sorted(_MODEL_PATHS) == sorted(MODEL_FIELDS), "a model field has no JSON path"

# The invariants are constraints, not conventions: a row that cannot be true
# cannot be stored, whatever the writer believes.
_SCHEMA = f"""
CREATE TABLE runs (
    run_id        TEXT PRIMARY KEY,
    repo_url      TEXT NOT NULL,
    auditor       TEXT NOT NULL,
    options       TEXT NOT NULL,
    started_at    TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ({','.join(f"'{s}'" for s in RUN_STATUSES)})),
    finished_at   TEXT,
    seconds       REAL,
    stages        TEXT NOT NULL,
    app           TEXT,
    artifacts_dir TEXT,
    finding_count INTEGER,
    surface_count INTEGER,
    error         TEXT,
    uploads       TEXT NOT NULL,
    envelope      TEXT,
    CHECK ((status = 'finished') = (envelope IS NOT NULL)),
    CHECK ((status = 'failed') = (error IS NOT NULL)),
    CHECK ((status = 'running') = (finished_at IS NULL))
);
CREATE INDEX runs_started_at ON runs (started_at DESC, run_id);
"""


class StoreRefused(RuntimeError):
    """The database on disk is not one this code will read or write."""


@dataclass(frozen=True)
class HistoryStore:
    """Every past run, addressed by the file that holds them."""

    path: Path

    def save(self, record: RunRecord, envelope: dict | None = None) -> None:
        """Write a run, replacing any earlier state of the same run."""
        row = to_columns(record, envelope)
        columns = ",".join(_COLUMNS)
        marks = ",".join("?" for _ in _COLUMNS)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(f"INSERT OR REPLACE INTO runs ({columns}) VALUES ({marks})",
                       [row[name] for name in _COLUMNS])

    def get(self, run_id: str) -> tuple[RunRecord, dict | None] | None:
        """One run and the envelope it stored, or None when no row has that id."""
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            found = db.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return None if found is None else from_columns(found)

    def recent(self, limit: int = HISTORY_LIST_LIMIT) -> list[RunRecord]:
        """The newest runs, without the envelopes they embed."""
        named = ",".join(DURABLE_FIELDS)
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                f"SELECT {named} FROM runs ORDER BY started_at DESC, run_id LIMIT ?",
                (limit,)).fetchall()
        return [from_columns(row)[0] for row in rows]

    def superseded(self, record: RunRecord) -> bool:
        """Whether a later run wrote over this one's artifacts.

        Any later run, not only a finished one: a run that started after this
        one and named the same directory has already begun writing into it.

        A run started from the browser writes under its own id from 2026-09-18
        (`run_files.RUN_ARTIFACTS_ROOT`), so no two such runs share a directory
        and this answers false for all of them. It is still asked, because rows
        recorded before that wrote to `artifacts/<system>/<app>/`, shared by
        every audit of the app: without it an old run's download would serve the
        newest run's bytes under the old run's timestamp, which is the history
        page and the download link lying to each other.
        """
        if record.artifacts_dir is None:
            return False
        return self.overwritten_since(record, record.artifacts_dir)

    def overwritten_since(self, record: RunRecord, directory: str) -> bool:
        """Whether a later run wrote to a named directory, whichever arm used it.

        `superseded` asks this about the record's own column. A
        `--compare-models` run's hosted arm writes to a path that is **not** a
        column -- only its envelope names it -- and that path is shared by every
        compare run of the same app exactly as `artifacts/<app>/` is shared by
        every audit of it. Without this, the hosted arm's files would be served
        under an older run's timestamp, which is the one thing `SUPERSEDED`
        exists to refuse.

        `json_extract` over the stored envelope rather than a new column: the
        fact is already on disk, and a column would version the file to record
        something nothing else reads. Either arm of a later run counts, because
        either can be the one that overwrote this directory.
        """
        with closing(sqlite3.connect(self.path)) as db:
            later = db.execute(
                "SELECT 1 FROM runs WHERE run_id != ? AND started_at > ? "
                "AND (artifacts_dir = ? "
                "     OR json_extract(envelope, '$.comparison.artifacts_dir') = ?) "
                "LIMIT 1",
                (record.run_id, record.started_at, directory, directory)).fetchone()
        return later is not None

    def delete(self, run_id: str) -> bool:
        """Forget one run. True when a row went, False when none had that id.

        The answer is a count and not an assumption: `DELETE` on a missing row
        is silent success in SQL, so a caller told nothing cannot tell "removed"
        from "was never there" -- and the route above it turns exactly that
        difference into a 404.

        The row and nothing else *here*. Whether a run's files may go with it
        is a question about the filesystem, so `web/run_files.py` answers it and
        the route calls both: this method has never had a status guard either,
        and keeping both rules out of the store leaves each of them in one
        place.
        """
        with closing(sqlite3.connect(self.path)) as db, db:
            return db.execute("DELETE FROM runs WHERE run_id = ?",
                              (run_id,)).rowcount > 0

    def clear(self) -> int:
        """Forget every run. Returns how many rows went.

        Unlike `delete`, this does not care about status: it is the one
        operation a reader asks for *because* they want the finished runs gone
        too. The narrowing that protects a single row is on the route above,
        not here -- the store has never had a status guard, and giving it one
        would put the rule in two places.

        The rows and nothing else, for the same reason `delete` says: nothing
        under `artifacts/` or `runs/uploads/` is keyed on a run in a way that
        makes deleting it safe from here.
        """
        with closing(sqlite3.connect(self.path)) as db, db:
            return db.execute("DELETE FROM runs").rowcount

    def model_run(self, run_id: str) -> dict:
        """What answered for each arm of one run, out of its stored envelope.

        Four values, every one nullable. `json_extract` returns NULL for a
        missing envelope and for a missing key alike, so "still running",
        "finished but wrote no findings.json" and "had no second arm" all arrive
        as null with no branch here. The caller renders the difference between
        them; this reports it.

        One query per row rather than one for the page: fifty indexed lookups
        against a local SQLite file is not a measured problem, and a batched
        `IN (?, ?, ...)` would be a second code path for the single-run route to
        disagree with.
        """
        named = ", ".join(f"json_extract(envelope, '{_MODEL_PATHS[field]}')"
                          for field in MODEL_FIELDS)
        with closing(sqlite3.connect(self.path)) as db:
            found = db.execute(f"SELECT {named} FROM runs WHERE run_id = ?",
                               (run_id,)).fetchone()
        return dict(zip(MODEL_FIELDS, found or (None,) * len(MODEL_FIELDS)))

    def count(self) -> int:
        """How many runs the store holds, which is not how many it just listed."""
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute("SELECT count(*) FROM runs").fetchone()[0]


def open_store(directory: Path | None = None, create: bool = False) -> HistoryStore:
    """Open the store, or refuse and say exactly why. Creates nothing unless asked.

    `create` is explicit for the reason `src/retrieval/store.py` makes it
    explicit: connecting is not a read. A caller that has not decided to make a
    database should not make one by asking whether it exists.

    `directory` defaults to `STORE_DIR` at *call* time, not in the signature: a
    default evaluated when this function was defined cannot be redirected by
    anything that imports the module, which made the store impossible to point
    somewhere else without reaching into `__defaults__`.
    """
    # Resolved whatever was passed, so a caller's relative path cannot be
    # invalidated later by a change of working directory.
    path = ((STORE_DIR if directory is None else directory) / STORE_NAME).resolve()
    if not path.is_file():
        if not create:
            raise StoreRefused(
                f"no run history at {path}; open it with create=True to start one")
        path.parent.mkdir(parents=True, exist_ok=True)
        return _created(path)
    found = _version_of(path)
    if found != STORE_SCHEMA_VERSION:
        raise StoreRefused(
            f"{path} is a run history at version {found}, and this code reads "
            f"version {STORE_SCHEMA_VERSION}. It is never migrated and never "
            "deleted -- that file is untouched and still readable with any "
            "sqlite3 client. Move it aside to start a new one.")
    store = HistoryStore(path)
    _reconcile(store)
    return store


def _created(path: Path) -> HistoryStore:
    """Make an empty store at a path nothing holds yet."""
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript(_SCHEMA)
        # A bound parameter is not allowed in a PRAGMA value, so this is
        # interpolated -- from a constant in this module, never from a request.
        db.execute(f"PRAGMA user_version = {STORE_SCHEMA_VERSION}")
    return HistoryStore(path)


def _version_of(path: Path) -> int:
    """The version an existing file declares, refusing anything unreadable."""
    try:
        with closing(sqlite3.connect(path)) as db:
            return db.execute("PRAGMA user_version").fetchone()[0]
    except sqlite3.DatabaseError as error:
        raise StoreRefused(f"{path} is not a readable SQLite database: {error}") from error


def _reconcile(store: HistoryStore) -> None:
    """Fail every run left `running` by a server that stopped.

    Only the process that owns a run can honestly call it running. Without
    this, a killed server leaves rows that spin in the history view for ever --
    a gap rendered as work in progress, which is the failure this whole project
    is about.
    """
    with closing(sqlite3.connect(store.path)) as db, db:
        db.execute(
            "UPDATE runs SET status = ?, error = ?, finished_at = ? WHERE status = ?",
            (FAILED, INTERRUPTED, now(), RUNNING))
