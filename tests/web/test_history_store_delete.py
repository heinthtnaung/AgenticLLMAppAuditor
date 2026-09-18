"""Forgetting one row: the store answers with a count, not with an assumption.

`HistoryStore.delete` is the one operation in this project that destroys durable
state, and it is two lines. The subject here is the return value rather than the
SQL: **`DELETE` on a row that is not there is silent success in SQLite**, so a
method that answered `None` would leave its caller unable to tell "removed" from
"was never there" -- and the route above it turns exactly that difference into
the difference between a 200 and a 404. The docstring on `delete` claims the
rowcount is what it reports; the third test below is what makes that claim
checkable rather than a comment.

**What it may not take with it.** A row, and nothing else: no file, and no other
row. `artifacts/<app>/` is keyed on the app name and shared with every other run
of that app, so a store that deleted a run's files would take a different run's
evidence with them.

**Both halves are measured, and for a while only one was.** This paragraph used
to claim the file half was "asserted here as *the directory this store was told
about is still there*" -- and nothing in the file created a directory, imported
a path or touched the filesystem at all. A docstring claiming coverage that does
not exist is this project's own subject one file deep, so the test was written
rather than the sentence cut. It is the only place the claim can be made at
store level: `test_run_delete.py` reads the `artifacts_current` flag, which is a
fact about rows, not about bytes; and which runs a directory belongs to is
`test_failed_run_has_no_artifacts_dir.py`.

Every store here is built under `tmp_path` by `run_rows.a_store`, and the one
artifact directory is written there too, so neither the checkout's own
`runs/history.sqlite3` nor its `artifacts/` is ever touched. Nothing skips:
`history_store.py` is free of fastapi on purpose, and this file is the reason
that is worth keeping true.
"""

from .run_rows import ENVELOPE, a_store, failed, finished, running

# Three ids, so "the right row went" is a comparison and not an inspection of
# one row on its own.
FIRST = "a" * 32
SECOND = "b" * 32
THIRD = "c" * 32

# A well-formed id nobody stored. The store does not check the shape -- that is
# the route's job -- so this is about the row, not about the id.
UNUSED = "0" * 32

# What three rows become when one goes.
STORED = 3
LEFT_AFTER_ONE_DELETE = 2

# One artifact a run left on disk, so "no file went with the row" is read back
# rather than inferred from a directory still existing.
ARTIFACT_NAME = "findings.json"
ARTIFACT_BYTES = '{"finding_count": 4}'


def store_with_three(tmp_path):
    """A history holding one failed, one finished and one running run."""
    store = a_store(tmp_path)
    store.save(failed(FIRST))
    store.save(finished(SECOND), ENVELOPE)
    store.save(running(THIRD))
    return store


# --- the row goes ---------------------------------------------------------------

def test_a_failed_row_is_gone_after_it_is_deleted(tmp_path) -> None:
    """The whole feature in one line: the run the page forgot no longer answers."""
    store = a_store(tmp_path)
    store.save(failed(FIRST))
    store.delete(FIRST)
    assert store.get(FIRST) is None


def test_the_count_drops_by_exactly_one(tmp_path) -> None:
    """`stored_run_count` is read off this, so a delete that took two rows would show here."""
    store = store_with_three(tmp_path)
    assert store.count() == STORED
    store.delete(FIRST)
    assert store.count() == LEFT_AFTER_ONE_DELETE


def test_deleting_one_row_leaves_every_other_row_alone(tmp_path) -> None:
    """Named rather than counted: a count cannot say *which* two survived."""
    store = store_with_three(tmp_path)
    store.delete(FIRST)
    assert sorted(record.run_id for record in store.recent()) == [SECOND, THIRD]


def test_a_forgotten_row_leaves_the_history_list_too(tmp_path) -> None:
    """The list is the page's own view, and it is a second query from `get`."""
    store = store_with_three(tmp_path)
    store.delete(FIRST)
    assert FIRST not in [record.run_id for record in store.recent()]


# --- the answer is a count, not an assumption ----------------------------------

def test_deleting_a_row_that_was_there_answers_true(tmp_path) -> None:
    """The half the route reads as "removed"."""
    store = a_store(tmp_path)
    store.save(failed(FIRST))
    assert store.delete(FIRST) is True


def test_deleting_an_id_no_row_carries_answers_false(tmp_path) -> None:
    """The claim in the method's own docstring: SQL's silent success is not reported as one."""
    assert a_store(tmp_path).delete(UNUSED) is False


def test_deleting_the_same_row_twice_answers_false_the_second_time(tmp_path) -> None:
    """Non-vacuity on the pair above: the same call answers both ways, by state alone."""
    store = a_store(tmp_path)
    store.save(failed(FIRST))
    assert [store.delete(FIRST), store.delete(FIRST)] == [True, False]


def test_a_delete_that_found_nothing_changes_nothing(tmp_path) -> None:
    """A `False` is not a partial delete: every row is still there."""
    store = store_with_three(tmp_path)
    store.delete(UNUSED)
    assert store.count() == STORED


# --- and it takes no file with it ----------------------------------------------

def test_deleting_a_row_leaves_the_files_that_run_wrote(tmp_path) -> None:
    """The row and nothing else: `artifacts/<app>/` is shared with every other run of that app.

    Read back rather than tested for existence, so a file truncated in passing
    fails as loudly as one removed.
    """
    written = tmp_path / "artifacts" / "agentic_auditor" / "demo-app"
    written.mkdir(parents=True)
    (written / ARTIFACT_NAME).write_text(ARTIFACT_BYTES, encoding="utf-8")
    store = a_store(tmp_path)
    store.save(finished(SECOND, artifacts_dir=str(written)), ENVELOPE)
    store.delete(SECOND)
    assert (written / ARTIFACT_NAME).read_text(encoding="utf-8") == ARTIFACT_BYTES


def test_that_run_really_was_forgotten(tmp_path) -> None:
    """Non-vacuity: a delete that did nothing at all would leave the file too."""
    written = tmp_path / "artifacts" / "agentic_auditor" / "demo-app"
    written.mkdir(parents=True)
    (written / ARTIFACT_NAME).write_text(ARTIFACT_BYTES, encoding="utf-8")
    store = a_store(tmp_path)
    store.save(finished(SECOND, artifacts_dir=str(written)), ENVELOPE)
    assert store.delete(SECOND) is True
    assert store.get(SECOND) is None


# --- the store decides nothing about which rows may go -------------------------

def test_the_store_removes_a_finished_row_when_it_is_told_to(tmp_path) -> None:
    """The narrowing to `failed` is the route's rule, and this says where it does not live.

    Written down because a second copy of the rule here would be the kind of
    duplication this project spends its design refusing -- and because a reader
    who assumed the store enforced it could move the route's check and lose it
    entirely with the suite green.
    """
    store = a_store(tmp_path)
    store.save(finished(SECOND), ENVELOPE)
    assert store.delete(SECOND) is True
