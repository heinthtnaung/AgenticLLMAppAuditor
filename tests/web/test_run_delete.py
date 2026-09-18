"""Forgetting a run: one status may go, the other two are refused by name.

`DELETE /api/runs/{run_id}` is the only endpoint this project has that destroys
durable state, and the whole of its safety is a narrowing: **a failed run, and
nothing else.** So what is asserted here is not only that a failed row goes, but
that each of the other two statuses is refused *and is still readable
afterwards* -- a refusal that answered 409 and deleted the row anyway would pass
a test that only read the status code.

**409 rather than 400, and that distinction is the subject of two tests.** The
request is well formed; it is the run's *state* that refuses it, which is the
same reason `POST /api/audit` answers 409 while an audit is in flight and
`downloads.py` answers 409 for a superseded run. A 400 would tell a caller to
fix the request, and there is nothing in the request to fix.

**"By name" is asserted as the clause that names it, not as a substring of the
sentence.** `assert record.status in detail` held for the wrong reason: the
detail *explains* both refusals -- "a finished run's envelope is the only copy
... and a running one still has a worker" -- so the words "finished" and
"running" are both in it whatever run was asked for. `f"this run is not failed"`
passed, in a file whose own title promises the other statuses are refused **by
name**. So the status is joined to its own clause, and the two refusals are
required to differ from each other: one sentence serving both is what the naive
check could not see. This is the behavioural instance of a fault the file
sweeps kept finding in JSX -- "is presence the claim?" has to be asked of an
assertion over a *response body* too, not only of one that reads a file.

**Which ids the route accepts is `test_run_delete_ids.py`** -- the unknown one,
the malformed ones, and the guard that keeps them out of the store. A different
question from this one: that file mirrors `test_run_routes.py`'s treatment of
the same `RUN_ID` pattern on the GET and shares `MALFORMED_IDS` with it, while
this file is about a run's *state*. They were one file until it passed the
~200-line rule, and the seam was already drawn in its own section comments.

**Forgetting a failed run moves no other run's `artifacts_current`.** That
flag is computed per request from the store, so a delete is exactly the kind of
change that could move it. It cannot here, because a failed row names no
`artifacts_dir` -- which is prose in the route's docstring and a measurement in
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
NOT_FAILED = 409

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

# How the refusal names the run it refused: the status, followed by the comma
# that ends its clause. The rest of the sentence explains *both* statuses, so
# the bare word is in every detail whichever run was asked for.
THE_STATUS_CLAUSE = "this run is {status},"

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


# --- and no other status may ----------------------------------------------------

@pytest.mark.parametrize("run_id", [FINISHED_ID, RUNNING_ID])
def test_a_run_that_is_not_failed_is_refused_with_409(tmp_path, run_id) -> None:
    """Well-formed request, refusing state: the distinction `ALREADY_RUNNING` already draws."""
    client, _ = client_holding_all_three(tmp_path)
    assert client.delete(f"{RUNS}/{run_id}").status_code == NOT_FAILED


@pytest.mark.parametrize("run_id", [FINISHED_ID, RUNNING_ID])
def test_a_refused_run_is_still_there_afterwards(tmp_path, run_id) -> None:
    """The half a status code cannot see: a 409 that deleted the row anyway would pass above."""
    client, _ = client_holding_all_three(tmp_path)
    client.delete(f"{RUNS}/{run_id}")
    assert read_run(client, run_id)["run_id"] == run_id
    assert stored_run_count(client) == STORED


def test_a_refused_finished_run_still_has_its_envelope(tmp_path) -> None:
    """Why it is refused at all: that envelope is the only copy of its findings."""
    client, _ = client_holding_all_three(tmp_path)
    client.delete(f"{RUNS}/{FINISHED_ID}")
    assert read_run(client, FINISHED_ID)["result"] == ENVELOPE


@pytest.mark.parametrize("run_id", [FINISHED_ID, RUNNING_ID])
def test_the_refusal_names_the_status_it_refused(tmp_path, run_id) -> None:
    """In its own clause: the rest of the sentence names both statuses whatever was asked."""
    client, _ = client_holding_all_three(tmp_path)
    detail = client.delete(f"{RUNS}/{run_id}").json()["detail"]
    status = read_run(client, run_id)["status"]
    assert THE_STATUS_CLAUSE.format(status=status) in detail


def test_the_two_refusals_do_not_say_the_same_thing(tmp_path) -> None:
    """One sentence serving both runs is exactly what a substring check cannot see."""
    client, _ = client_holding_all_three(tmp_path)
    said = [client.delete(f"{RUNS}/{run_id}").json()["detail"]
            for run_id in (FINISHED_ID, RUNNING_ID)]
    assert said[0] != said[1]


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
