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
    DURABLE_FIELDS, ENVELOPE, FAILED, INTERRUPTED, RUNNING, RUN_STATUSES,
    RunRecord, from_columns, now, to_columns)

# The file's own version, unrelated to the wire's: one versions a file, the
# other versions a protocol. Held in `PRAGMA user_version` rather than a table
# because a table must be *found* before it can be read, so `SELECT ... FROM
# meta` raises on exactly the files whose schema you are trying to detect.
# The pragma answers 0 for any SQLite file ever written, which makes "0 means
# not ours, or not initialised" a total answer instead of an exception.
STORE_SCHEMA_VERSION = 1

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

# The invariants are constraints, not conventions: a row that cannot be true
# cannot be stored, whatever the writer believes.
_SCHEMA = f"""
CREATE TABLE runs (
    run_id        TEXT PRIMARY KEY,
    repo_url      TEXT NOT NULL,
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

        Artifacts are keyed on the app name, not on the run, so two audits of
        one URL share `artifacts/<system>/<app>/`. Without this, an old run's
        download would serve the newest run's bytes under the old run's
        timestamp -- the history page and the download link lying to each other.
        """
        if record.artifacts_dir is None:
            return False
        with closing(sqlite3.connect(self.path)) as db:
            later = db.execute(
                "SELECT 1 FROM runs WHERE artifacts_dir = ? AND run_id != ? "
                "AND started_at > ? LIMIT 1",
                (record.artifacts_dir, record.run_id, record.started_at)).fetchone()
        return later is not None

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
            "deleted: move that file aside to start a new one.")
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
