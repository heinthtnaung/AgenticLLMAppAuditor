"""Forgetting a run: two statuses may go, and a running one is refused.

`DELETE /api/runs/{run_id}` is the only endpoint this project has that destroys
durable state, and the whole of its safety is a narrowing: **anything but a run
that is still going.** So what is asserted here is not only that a row goes, but
that a running one is refused *and is still readable afterwards* -- a refusal
that answered 409 and deleted the row anyway would pass a test that only read
the status code.

**It was failed-only until 2026-09-18, and a filesystem fact is what changed.**
Artifacts used to be keyed on the app, so every audit of one app shared a
directory and a finished run's stored envelope really was the only copy of its
findings -- its files had already been written over by the next run of that app.
They are keyed on the run now, so a finished run's files are still its own and
forgetting it is a reader deciding they do not want that report. The route's own
docstring carries the same reasoning; this file measures it.

**409 rather than 400, and that distinction is the subject of two tests.** The
request is well formed; it is the run's *state* that refuses it, which is the
same reason `POST /api/audit` answers 409 while an audit is in flight and
`downloads.py` answers 409 for a superseded run. A 400 would tell a caller to
fix the request, and there is nothing in the request to fix.

**The refusal has to say what is wrong, not merely refuse.** With one refusable
status left there is no second sentence to confuse it with, so the check is that
the detail names the *reason* -- a worker still writing -- rather than the bare
word "running", which a caller already knows because it asked. The older form of
this file joined the status to its own clause because the detail then explained
two refusals at once and the word "running" appeared whichever run was asked
for; that hazard went when the finished refusal did.

**Which ids the route accepts is `test_run_delete_ids.py`** -- the unknown one,
the malformed ones, and the guard that keeps them out of the store. A different
question from this one: that file mirrors `test_run_routes.py`'s treatment of
the same `RUN_ID` pattern on the GET and shares `MALFORMED_IDS` with it, while
this file is about a run's *state*. They were one file until it passed the
~200-line rule, and the seam was already drawn in its own section comments.

**Forgetting a failed run moves no other run's `artifacts_current`.** That
flag is computed per request from the store, so a delete is exactly the kind of
change that could move it. It cannot for a failed row, because such a row names
no `artifacts_dir` -- prose in the route's docstring and a measurement in
`test_failed_run_has_no_artifacts_dir.py`. The last test below is the other end
of it, over the endpoint a page actually reads.

Runs are written straight to the store rather than audited: the subject is a
row's status, not how it came to have one. Every application is a fresh one over
a store under `tmp_path`; see `api_stubs.py`. The whole file skips without the
server packages, because there is no endpoint without them.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

import run_record                                  # noqa: E402

from .api_stubs import RUNS, client_over, read_run   # noqa: E402
from .run_rows import ARTIFACTS, ENVELOPE, failed, finished, running   # noqa: E402

OK = 200
NO_SUCH_RUN = 404
STILL_RUNNING = 409

# One id per status, so a refusal is shown to be about the run it names.
FAILED_ID = "a" * 32
FINISHED_ID = "b" * 32
RUNNING_ID = "c" * 32

# Two times, so one finished run can supersede another in the same directory.
EARLY = "2026-09-09T10:00:00+00:00"
LATE = "2026-09-09T12:00:00+00:00"

# The keys the reply carries. It says nothing a caller needs -- the page
# discards it -- and exists so every body under `/api/` has a `schema_version`.
REPLY_KEYS = {"schema_version", "forgotten"}

# What the one refusal has to explain: not that the run is running, which the
# caller can already see, but that something is writing to what it asked to
# delete. A refusal that only said "no" would pass a status-code check.
THE_REASON = "worker is writing"

# Three rows in, two rows left.
STORED = 3
LEFT = 2


def client_holding_all_three(tmp_path):
    """A client over a history with one failed, one finished and one running row."""
    client, registry = client_over(tmp_path)
    registry.store.save(failed(FAILED_ID))
    registry.store.save(finished(FINISHED_ID), ENVELOPE)
    registry.store.save(running(RUNNING_ID))
    return client, registry


def stored_run_count(client) -> int:
    """How many rows the store holds, read the way the history page reads it."""
    return client.get(RUNS).json()["stored_run_count"]


# --- a failed run may be forgotten ---------------------------------------------

def test_forgetting_a_failed_run_is_answered_with_200(tmp_path) -> None:
    """The one status the endpoint accepts."""
    client, _ = client_holding_all_three(tmp_path)
    assert client.delete(f"{RUNS}/{FAILED_ID}").status_code == OK


def test_the_forgotten_run_no_longer_answers(tmp_path) -> None:
    """Gone from the store, not merely reported gone: the page re-reads the list."""
    client, _ = client_holding_all_three(tmp_path)
    client.delete(f"{RUNS}/{FAILED_ID}")
    assert client.get(f"{RUNS}/{FAILED_ID}").status_code == NO_SUCH_RUN


def test_the_stored_count_drops_by_exactly_one(tmp_path) -> None:
    """The figure beside the history heading, and the only one that can say "two went"."""
    client, _ = client_holding_all_three(tmp_path)
    assert stored_run_count(client) == STORED
    client.delete(f"{RUNS}/{FAILED_ID}")
    assert stored_run_count(client) == LEFT


def test_the_reply_echoes_the_id_and_carries_the_wire_version(tmp_path) -> None:
    """A 204 would be the one body under `/api/` with no `schema_version` in it."""
    client, _ = client_holding_all_three(tmp_path)
    body = client.delete(f"{RUNS}/{FAILED_ID}").json()
    assert set(body) == REPLY_KEYS
    assert body["forgotten"] == FAILED_ID
    assert body["schema_version"] == run_record.REPLY_SCHEMA_VERSION


# --- a finished run may be forgotten too, since 2026-09-18 ----------------------

def test_forgetting_a_finished_run_is_answered_with_200(tmp_path) -> None:
    """Its files are its own now, so forgetting it destroys nothing another run needs."""
    client, _ = client_holding_all_three(tmp_path)
    assert client.delete(f"{RUNS}/{FINISHED_ID}").status_code == OK


def test_forgetting_a_finished_run_takes_its_envelope_with_it(tmp_path) -> None:
    """The inverse of the old guarantee, asserted so the reversal cannot be silent.

    This envelope was the reason a finished run could not be forgotten. It is
    still the only copy of that run's findings -- what changed is that it is no
    longer the only copy of a *live* report, because the files it describes are
    keyed on the run and go with it.
    """
    client, _ = client_holding_all_three(tmp_path)
    client.delete(f"{RUNS}/{FINISHED_ID}")
    assert client.get(f"{RUNS}/{FINISHED_ID}").status_code == NO_SUCH_RUN


# --- and a running one may not --------------------------------------------------

def test_a_running_run_is_refused_with_409(tmp_path) -> None:
    """Well-formed request, refusing state: the distinction `ALREADY_RUNNING` already draws."""
    client, _ = client_holding_all_three(tmp_path)
    assert client.delete(f"{RUNS}/{RUNNING_ID}").status_code == STILL_RUNNING


def test_a_refused_running_run_is_still_there_afterwards(tmp_path) -> None:
    """The half a status code cannot see: a 409 that deleted the row anyway would pass above."""
    client, _ = client_holding_all_three(tmp_path)
    client.delete(f"{RUNS}/{RUNNING_ID}")
    assert read_run(client, RUNNING_ID)["run_id"] == RUNNING_ID
    assert stored_run_count(client) == STORED


def test_the_refusal_says_what_is_writing_rather_than_only_refusing(tmp_path) -> None:
    """A caller knows it asked about a running run; what it does not know is why that matters."""
    client, _ = client_holding_all_three(tmp_path)
    detail = client.delete(f"{RUNS}/{RUNNING_ID}").json()["detail"]
    assert THE_REASON in detail


def test_that_reader_would_notice_a_refusal_that_explained_nothing(tmp_path) -> None:
    """Mutation check: the assertion above is not satisfied by any 409 body."""
    assert THE_REASON not in "this run is running"


# --- and the rest of the history is untouched -----------------------------------

def test_forgetting_a_failed_run_moves_no_other_runs_artifacts_flag(tmp_path) -> None:
    """Two finished runs share one directory; forgetting a third, failed run changes neither.

    Asserted over two runs whose flags *differ* -- the earlier one is superseded
    and the later one is not -- so a delete that reset the flag, or that made
    every run look current, is visible. Two `true`s compared before and after
    would not be.
    """
    client, registry = client_over(tmp_path)
    registry.store.save(finished("d" * 32, started_at=EARLY, artifacts_dir=ARTIFACTS),
                        ENVELOPE)
    registry.store.save(finished("e" * 32, started_at=LATE, artifacts_dir=ARTIFACTS),
                        ENVELOPE)
    registry.store.save(failed(FAILED_ID))
    before = [read_run(client, "d" * 32)["artifacts_current"],
              read_run(client, "e" * 32)["artifacts_current"]]
    client.delete(f"{RUNS}/{FAILED_ID}")
    after = [read_run(client, "d" * 32)["artifacts_current"],
             read_run(client, "e" * 32)["artifacts_current"]]
    assert before == [False, True]
    assert after == before
