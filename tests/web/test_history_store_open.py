"""Opening the run history: the five decisions made before a row is ever read.

`sqlite3.connect()` creates the file, exactly as `chromadb.PersistentClient`
does -- which is why `src/retrieval/store.py` checks for an index before opening
a client, and why this store copies that shape down to `create: bool = False`.
So "does it exist?" and "may I make one?" are two questions here, and each of
the five rows in `docs/SCHEMAS.md`'s opening table is one test below.

**"The path it holds" is a regression section.** `open_store` used to keep the
relative `STORE_DIR` it was given, so
any later `chdir` -- `web/serve.py` does one, and a test does one whenever an
audit must write into `tmp_path` -- pointed the store at a directory that does
not exist, and every later query raised `sqlite3.OperationalError: unable to
open database file`. It resolves at open now; both tests there open a
*relative* directory and then move the working directory, because handed an
absolute one a store that kept what it was given looks correct and still
breaks -- which is how the defect survived being tested the first time.

Nothing here skips: `history_store.py` is free of fastapi on purpose, so the
durable half of the wrapper is testable on a clean checkout. Every database is
built under `tmp_path`; `tests/web/__init__.py` keeps the checkout's own
`runs/history.sqlite3` out of reach besides.
"""

import sqlite3
from pathlib import Path

import pytest

import history_store
from history_store import (
    STORE_NAME, STORE_SCHEMA_VERSION, HistoryStore, StoreRefused, open_store)
from run_record import FAILED, INTERRUPTED, RUNNING, RunRecord

# The version this code reads, pinned as a literal beside the constant it must
# equal. Imported alone it would agree with itself. It went to 2 when the record
# gained a required `auditor`.
EXPECTED_STORE_SCHEMA_VERSION = 2

# The version this code used to write, and the one a checkout that ran the
# server before today has on disk. The refusal a real person meets.
PREVIOUS_VERSION = 1

# A version no release of this code ever wrote, so the refusal is about the
# number and not about the file being unreadable.
FOREIGN_VERSION = 9

# What the refusal must say beyond the two numbers: the old file is still there.
# It is the only copy of that history, and a message that did not say so invites
# the reader to assume it was migrated or replaced.
NOT_DELETED = "never deleted"

# Bytes that are not a database, which is what `_version_of` has to wrap rather
# than let out as a bare `sqlite3.DatabaseError`.
NOT_A_DATABASE = "this is a text file that happens to have the right name"

RUN_ID = "b" * 32
URL = "https://example.invalid/owner/demo-app"
AUDITOR = "Quokka Reviewer"
WHEN = "2026-09-09T12:00:00+00:00"
OPTIONS = {"url": URL}

# Somewhere to stand while checking that the store no longer cares where we are.
ELSEWHERE = "a-different-working-directory"

# This checkout, which is where `history_store.STORE_DIR` points when nothing
# has rebound it -- and so the one place a test's database may not land.
REPO_ROOT = Path(__file__).resolve().parents[2]

# The directory name `history_store.STORE_DIR` ends in, opened relative below on
# purpose: an absolute path would not show that the store resolves what it is
# handed.
RELATIVE_DIR = "runs"


def store_directory(tmp_path: Path) -> Path:
    """The directory a store would live in, deliberately not created."""
    return tmp_path / "runs"


def a_running_row(store: HistoryStore) -> None:
    """Store one run that says `running`, as a server that then stopped would leave it."""
    store.save(RunRecord(run_id=RUN_ID, repo_url=URL, auditor=AUDITOR,
                         options=OPTIONS, started_at=WHEN))


def foreign_database(tmp_path: Path, version: int) -> Path:
    """A SQLite file some other writer made, declaring a version this code does not read."""
    directory = store_directory(tmp_path)
    directory.mkdir()
    with sqlite3.connect(directory / STORE_NAME) as db:
        db.execute(f"PRAGMA user_version = {version}")
    return directory


# --- file absent ---------------------------------------------------------------

def test_a_missing_history_is_refused_when_creating_was_not_asked_for(tmp_path) -> None:
    """Connecting is not a read: a caller that has not decided to make one must not."""
    with pytest.raises(StoreRefused, match="no run history at"):
        open_store(store_directory(tmp_path))


def test_the_refusal_to_create_leaves_nothing_behind(tmp_path) -> None:
    """The trap this shape exists for: asking whether it exists must not make it exist."""
    with pytest.raises(StoreRefused):
        open_store(store_directory(tmp_path))
    assert not store_directory(tmp_path).exists()


def test_the_refusal_names_the_path_and_how_to_start_one(tmp_path) -> None:
    """A refusal at startup is fatal, so it has to say which file and what to do."""
    with pytest.raises(StoreRefused, match="create=True") as refused:
        open_store(store_directory(tmp_path))
    assert str(store_directory(tmp_path) / STORE_NAME) in str(refused.value)


def test_creating_writes_the_file_the_table_and_the_version(tmp_path) -> None:
    """The one path allowed to make a new database, and it makes a complete one."""
    store = open_store(store_directory(tmp_path), create=True)
    assert store.path.is_file()
    with sqlite3.connect(store.path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == STORE_SCHEMA_VERSION
        assert db.execute("SELECT count(*) FROM runs").fetchone()[0] == 0


def test_creating_makes_the_directory_it_was_pointed_at(tmp_path) -> None:
    """`runs/` is gitignored and need not exist yet; a first run should not have to mkdir."""
    open_store(store_directory(tmp_path), create=True)
    assert store_directory(tmp_path).is_dir()


# --- the path it holds ---------------------------------------------------------

def test_a_relative_directory_is_resolved_to_an_absolute_path_at_open(monkeypatch,
                                                                      tmp_path) -> None:
    """`api.py`'s own case: it opens `runs/` relative, and `serve.py` then chdirs.

    Opened *relative* on purpose. Handed an absolute directory, a store that
    kept what it was given would look correct here and still break the moment
    the process moved -- which is how the defect below survived being tested.
    """
    monkeypatch.chdir(tmp_path)
    store = open_store(Path(RELATIVE_DIR), create=True)
    assert store.path.is_absolute()
    assert store.path == tmp_path / RELATIVE_DIR / STORE_NAME


def test_a_store_still_reads_and_writes_after_the_process_moves(monkeypatch,
                                                                tmp_path) -> None:
    """The regression: a `chdir` used to make every query `unable to open database file`."""
    monkeypatch.chdir(tmp_path)
    store = open_store(Path(RELATIVE_DIR), create=True)
    moved_to = tmp_path / ELSEWHERE
    moved_to.mkdir()
    monkeypatch.chdir(moved_to)
    a_running_row(store)
    assert store.get(RUN_ID) is not None
    assert store.count() == 1


def test_a_caller_that_names_no_directory_reads_the_module_constant_at_call_time() -> None:
    """`api.py`'s own call, and the only mechanism `tests/web/__init__.py` redirects it with.

    `open_store()` resolves `STORE_DIR` when it is called, so rebinding that
    module constant moves the file for the caller that passes no directory.
    Bound as a default argument instead -- as it once was -- this suite would
    open the checkout's own `runs/history.sqlite3`, and `_reconcile` would fail
    every run a real server had left running in it.
    """
    store = open_store(create=True)
    assert store.path == (history_store.STORE_DIR / STORE_NAME).resolve()
    assert REPO_ROOT not in store.path.parents


# --- file present and not ours -------------------------------------------------

def test_the_store_version_is_the_one_this_code_writes() -> None:
    """The file's own version, unrelated to the wire's: one versions a file, one a protocol."""
    assert STORE_SCHEMA_VERSION == EXPECTED_STORE_SCHEMA_VERSION


def test_a_history_written_by_the_previous_version_is_refused(tmp_path) -> None:
    """The refusal a real checkout meets, not a hypothetical one.

    It refuses rather than migrates, and the reasoning is the record's own:
    `options.model` would be honestly null on an old row and `uploads` honestly
    empty, but `auditor` has **no true value** -- nobody recorded who ran it,
    and a guessed name in a history list is the same fact-shaped guess this
    project refuses for `app`.
    """
    with pytest.raises(StoreRefused, match="never migrated"):
        open_store(foreign_database(tmp_path, PREVIOUS_VERSION))


def test_the_previous_version_refusal_names_both_versions(tmp_path) -> None:
    """Which number the file says and which this code reads, or the message is unactionable."""
    with pytest.raises(StoreRefused) as refused:
        open_store(foreign_database(tmp_path, PREVIOUS_VERSION))
    said = str(refused.value)
    assert f"version {PREVIOUS_VERSION}" in said
    assert f"version {STORE_SCHEMA_VERSION}" in said


def test_the_refusal_says_the_old_history_is_not_deleted(tmp_path) -> None:
    """The one thing a person needs to hear: their only copy of that history is intact."""
    with pytest.raises(StoreRefused, match=NOT_DELETED):
        open_store(foreign_database(tmp_path, PREVIOUS_VERSION))


def test_the_refused_file_is_still_there_and_still_says_what_it_said(tmp_path) -> None:
    """Non-vacuity for the sentence above: the message is checked against the disk."""
    directory = foreign_database(tmp_path, PREVIOUS_VERSION)
    with pytest.raises(StoreRefused):
        open_store(directory)
    assert (directory / STORE_NAME).is_file()
    with sqlite3.connect(directory / STORE_NAME) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == PREVIOUS_VERSION


def test_a_history_at_another_version_is_refused(tmp_path) -> None:
    """It never migrates: the grading key's precedent, with a page for a reader."""
    with pytest.raises(StoreRefused, match="never migrated"):
        open_store(foreign_database(tmp_path, FOREIGN_VERSION))


def test_the_version_refusal_names_both_versions_and_the_path(tmp_path) -> None:
    """Which file, what it says, and what this code reads -- or the message is unactionable."""
    directory = foreign_database(tmp_path, FOREIGN_VERSION)
    with pytest.raises(StoreRefused) as refused:
        open_store(directory)
    said = str(refused.value)
    assert f"version {FOREIGN_VERSION}" in said
    assert f"version {STORE_SCHEMA_VERSION}" in said
    assert str(directory / STORE_NAME) in said


def test_a_history_at_this_version_is_not_refused(tmp_path) -> None:
    """Non-vacuity: the two refusals above are about the number, not about opening at all."""
    open_store(store_directory(tmp_path), create=True)
    assert open_store(store_directory(tmp_path)).path.is_file()


def test_a_file_that_is_not_a_database_is_refused_by_this_modules_own_error(tmp_path) -> None:
    """Wrapped, not raw: a startup failure should name the file, not sqlite's opinion alone."""
    directory = store_directory(tmp_path)
    directory.mkdir()
    (directory / STORE_NAME).write_text(NOT_A_DATABASE, encoding="utf-8")
    with pytest.raises(StoreRefused, match="not a readable SQLite database"):
        open_store(directory)


def test_the_unreadable_file_refusal_names_the_path(tmp_path) -> None:
    """The same requirement as the other two: the operator has to know which file to move."""
    directory = store_directory(tmp_path)
    directory.mkdir()
    (directory / STORE_NAME).write_text(NOT_A_DATABASE, encoding="utf-8")
    with pytest.raises(StoreRefused) as refused:
        open_store(directory)
    assert str(directory / STORE_NAME) in str(refused.value)


# --- what opening reconciles ---------------------------------------------------

def test_a_run_left_running_by_a_previous_process_is_failed_on_open(tmp_path) -> None:
    """Only the process that owns a run can call it running; nobody owns this one."""
    a_running_row(open_store(store_directory(tmp_path), create=True))
    reopened = open_store(store_directory(tmp_path))
    record, _ = reopened.get(RUN_ID)
    assert record.status == FAILED
    assert record.error == INTERRUPTED


def test_the_reconciled_run_is_given_the_finish_time_it_lacked(tmp_path) -> None:
    """`failed` with no `finished_at` is a row the record itself refuses to be built from."""
    a_running_row(open_store(store_directory(tmp_path), create=True))
    record, _ = open_store(store_directory(tmp_path)).get(RUN_ID)
    assert record.finished_at is not None


def test_a_run_still_saying_running_before_the_reopen_is_what_was_reconciled(tmp_path) -> None:
    """Non-vacuity: the two tests above would pass if the row had never said `running`."""
    store = open_store(store_directory(tmp_path), create=True)
    a_running_row(store)
    record, _ = store.get(RUN_ID)
    assert record.status == RUNNING
