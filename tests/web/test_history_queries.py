"""The three questions a reader asks the run history: which, how new, how many.

`superseded`, `recent` and `count` are read paths, tested apart from the writes
in `test_history_rows.py`.

**`superseded` is asserted in both directions**, because a check that answered
"another run shares this directory" would pass the interesting case and then
refuse every older run's downloads for ever. Only a *later* run supersedes, and
a run that wrote no directory is never superseded by anything.

**`count()` against the list cap** is a test rather than an aside: the list is
`HISTORY_LIST_LIMIT` newest-first with no paging, and `stored_run_count` on the
list body is the total. A reader comparing the two is how they learn the history
is longer than the page shows.

Nothing here skips, and nothing here touches the checkout's own
`runs/history.sqlite3`: every database is built under `tmp_path`.
"""

from dataclasses import replace
from pathlib import Path

from history_store import HISTORY_LIST_LIMIT, HistoryStore, open_store
from run_record import RunRecord

URL = "https://example.invalid/owner/demo-app"
# Who asked for the run. Required since the wire version went to 3, so every
# record built here carries one.
AUDITOR = "Quokka Reviewer"
OPTIONS = {"url": URL, "semantic_probe": False}
ARTIFACTS = "artifacts/agentic_auditor/demo-app"
OTHER_ARTIFACTS = "artifacts/agentic_auditor/another-app"

# Three timestamps in the order they happened, so "newest first" has something
# to order. Seconds precision, as `run_record.now()` writes them.
EARLY = "2026-09-09T10:00:00+00:00"
MIDDLE = "2026-09-09T11:00:00+00:00"
LATE = "2026-09-09T12:00:00+00:00"

ENVELOPE = {"schema_version": 2, "app": "demo-app"}

# Two more than the cap, so the count and the list cannot come out equal.
STORED_OVER_THE_CAP = HISTORY_LIST_LIMIT + 2


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


def test_a_later_run_over_the_same_directory_supersedes_an_earlier_one(tmp_path) -> None:
    """Artifacts are keyed on the app, so two audits of one URL share a directory."""
    store = a_store(tmp_path)
    earlier = finished("a" * 32, started_at=EARLY)
    store.save(earlier, ENVELOPE)
    store.save(finished("b" * 32, started_at=LATE), ENVELOPE)
    assert store.superseded(earlier) is True


def test_the_later_run_is_not_itself_superseded(tmp_path) -> None:
    """The other half: only the older run's files were written over."""
    store = a_store(tmp_path)
    store.save(finished("a" * 32, started_at=EARLY), ENVELOPE)
    later = finished("b" * 32, started_at=LATE)
    store.save(later, ENVELOPE)
    assert store.superseded(later) is False


def test_a_run_alone_in_its_directory_is_not_superseded(tmp_path) -> None:
    """A store with one run in it must not refuse that run's own downloads."""
    store = a_store(tmp_path)
    only = finished("a" * 32)
    store.save(only, ENVELOPE)
    assert store.superseded(only) is False


def test_a_later_run_of_a_different_app_supersedes_nothing(tmp_path) -> None:
    """The join is on the directory, not on time alone."""
    store = a_store(tmp_path)
    earlier = finished("a" * 32, started_at=EARLY)
    store.save(earlier, ENVELOPE)
    store.save(finished("b" * 32, started_at=LATE, artifacts_dir=OTHER_ARTIFACTS), ENVELOPE)
    assert store.superseded(earlier) is False


def test_a_run_that_wrote_no_directory_is_never_superseded(tmp_path) -> None:
    """`artifacts_dir` is null on a run that failed early; nothing overwrote nothing."""
    store = a_store(tmp_path)
    accepted = running("a" * 32)
    store.save(accepted)
    store.save(finished("b" * 32, started_at=LATE), ENVELOPE)
    assert store.superseded(accepted) is False


# --- the newest few, and how many there are ------------------------------------

def test_the_list_is_newest_first(tmp_path) -> None:
    """What the history page shows, in the order it shows it."""
    store = a_store(tmp_path)
    for run_id, when in (("a" * 32, EARLY), ("b" * 32, LATE), ("c" * 32, MIDDLE)):
        store.save(running(run_id, when))
    assert [record.started_at for record in store.recent()] == [LATE, MIDDLE, EARLY]


def test_runs_that_started_in_the_same_second_are_ordered_by_id(tmp_path) -> None:
    """`(started_at DESC, run_id)` is a total order; seconds precision makes ties likely."""
    store = a_store(tmp_path)
    for run_id in ("b" * 32, "a" * 32, "c" * 32):
        store.save(running(run_id, LATE))
    assert [record.run_id for record in store.recent()] == ["a" * 32, "b" * 32, "c" * 32]


def test_the_list_carries_whole_records(tmp_path) -> None:
    """The list query names its columns and never selects `envelope`; the rest is the record."""
    store = a_store(tmp_path)
    record = finished("a" * 32)
    store.save(record, ENVELOPE)
    assert store.recent() == [record]


def test_the_list_is_capped_and_the_count_is_not(tmp_path) -> None:
    """The pair a reader compares: the page shows a view, the count is the history."""
    store = a_store(tmp_path)
    for index in range(STORED_OVER_THE_CAP):
        store.save(running(f"{index:032x}", LATE))
    assert store.count() == STORED_OVER_THE_CAP
    assert len(store.recent()) == HISTORY_LIST_LIMIT


def test_an_empty_history_lists_nothing_and_counts_zero(tmp_path) -> None:
    """The first request a fresh server answers, which must not be an error."""
    store = a_store(tmp_path)
    assert store.recent() == []
    assert store.count() == 0
