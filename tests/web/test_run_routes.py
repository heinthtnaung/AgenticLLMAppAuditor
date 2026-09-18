"""The three GETs and what the POST answers with: one shape, and one 404 that is a guard.

`POST /api/audit` returns 202 and a run record now, and the page polls
`GET /api/runs/{run_id}` for the same shape later in the same run's life. So
this file asserts the *protocol*: what acceptance answers with, what a poll
answers with, what the list carries, and what the stage vocabulary is.

**`GET /api/stages` is the test that stops the JavaScript restating a closed
vocabulary.** The page needs the whole list to show what has *not* happened yet,
and a second copy of `progress.STAGES` across a language boundary is how the two
copies start disagreeing -- the defect this project already records about the JSX
rebuilding a probe id.

**A malformed run id is 404, not 500.** "No run has that id" is true of `../..`
as much as of an id nobody used, and checking the shape keeps a request-supplied
string out of a filesystem join -- `web/downloads.py` builds a path from the
directory that id chooses.

The status code alone cannot see that guard, which is worth saying because it
was written that way first: with the shape check deleted the store is simply
asked for the malformed id, finds nothing, and the route answers the same 404.
So the guard is measured where it acts, against a store double that records
every id it was asked for -- the malformed ones must never reach it. That double
is `api_stubs.StoreThatRecordsLookups`, shared with `test_run_delete.py`, which
makes the same measurement of the same guard on `DELETE`.

**Forgetting a run is not in this file.** `DELETE /api/runs/{run_id}` is decided
by a run's *status* rather than by the protocol these four endpoints share, and
its refusals need three rows in three states to say anything -- so it is
`test_run_delete.py`. `MALFORMED_IDS` moved into `api_stubs.py` when that
happened: two routes apply the same pattern, and a list that grew in one file
would quietly leave the other testing less than its docstring claims.

Every application here is a fresh one over a store under `tmp_path`; see
`api_stubs.py` for why `api.app` is not used. The whole file skips when the
server packages are not installed: without fastapi there are no routes.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from dataclasses import replace                    # noqa: E402

import run_record                                  # noqa: E402
from history_store import HISTORY_LIST_LIMIT        # noqa: E402
from repo_url import canonical_url                  # noqa: E402
from reporting.progress import STAGES              # noqa: E402
from run_record import RUNNING, RunRecord          # noqa: E402

from .api_stubs import (                           # noqa: E402
    MALFORMED_IDS, RUNS, accepted_run_id, audit_and_poll, client_over,
    client_over_a_recording_store, poll_until_terminal, post_an_audit, read_run)
from .audit_stub import (                          # noqa: E402
    AUDITOR,    URL, stub_the_audit, wait_for_the_worker)

STAGES_PATH = "/api/stages"

OK = 200
NO_SUCH_RUN = 404
ACCEPTED = 202

# The eight boundaries an audit announces. Pinned as a count rather than
# re-listed: the vocabulary itself is `progress.STAGES`, and a second list here
# would be the very duplication this endpoint exists to prevent.
EXPECTED_STAGE_COUNT = 8

# A well-formed id nobody used, so the 404 above is shown to be about the row
# and not only about the shape.
UNUSED_ID = "0" * 32

# Two more than the page shows, so the count and the list cannot come out equal.
STORED_OVER_THE_CAP = HISTORY_LIST_LIMIT + 2

# The keys the list body carries, and the two a list row drops.
LIST_KEYS = {"schema_version", "stored_run_count", "runs"}
DROPPED_FROM_A_ROW = {"result", "schema_version"}

WHEN = "2026-09-09T12:00:00+00:00"


def a_stored_run(run_id: str) -> RunRecord:
    """One accepted run, written straight to the store rather than run."""
    return RunRecord(run_id=run_id, repo_url=URL, auditor=AUDITOR,
                     options={"url": URL}, started_at=WHEN)


# --- the stage vocabulary ------------------------------------------------------

def test_the_stage_endpoint_serves_the_whole_vocabulary_in_order(tmp_path) -> None:
    """Served rather than restated in JavaScript, so the two cannot disagree."""
    client, _ = client_over(tmp_path)
    assert client.get(STAGES_PATH).json()["stages"] == list(STAGES)


def test_the_stage_endpoint_carries_the_reply_version(tmp_path) -> None:
    """One constant for everything under `/api/`, so three bodies cannot claim three."""
    client, _ = client_over(tmp_path)
    assert client.get(STAGES_PATH).json()["schema_version"] == run_record.REPLY_SCHEMA_VERSION


def test_the_stage_vocabulary_is_the_eight_boundaries_an_audit_announces(tmp_path) -> None:
    """Non-vacuity: an empty tuple would satisfy the equality above."""
    client, _ = client_over(tmp_path)
    assert len(client.get(STAGES_PATH).json()["stages"]) == EXPECTED_STAGE_COUNT


# --- acceptance ----------------------------------------------------------------

def test_an_accepted_audit_is_answered_with_202(monkeypatch, tmp_path) -> None:
    """The endpoint does not block: it hands back a run and the page polls it."""
    stub_the_audit(monkeypatch, tmp_path)
    client, registry = client_over(tmp_path)
    assert post_an_audit(client).status_code == ACCEPTED
    wait_for_the_worker(registry)


def test_the_202_body_is_the_run_at_the_moment_it_was_accepted(monkeypatch,
                                                               tmp_path) -> None:
    """One shape, not two: `running`, nothing established, `stages` empty, no result."""
    stub_the_audit(monkeypatch, tmp_path)
    client, registry = client_over(tmp_path)
    body = post_an_audit(client).json()
    wait_for_the_worker(registry)
    assert body["status"] == RUNNING
    assert (body["stages"], body["result"], body["finished_at"]) == ([], None, None)


def test_the_202_body_is_the_same_keys_a_poll_answers_with(monkeypatch, tmp_path) -> None:
    """A page needs one parser, so acceptance and a poll may not differ by a key."""
    stub_the_audit(monkeypatch, tmp_path)
    client, registry = client_over(tmp_path)
    accepted = post_an_audit(client).json()
    wait_for_the_worker(registry)
    assert set(read_run(client, accepted["run_id"])) == set(accepted)


def test_a_polled_run_reaches_a_terminal_status(monkeypatch, tmp_path) -> None:
    """Non-vacuity for every poll in this folder: the background run really does end."""
    stub_the_audit(monkeypatch, tmp_path)
    client, _ = client_over(tmp_path)
    assert audit_and_poll(client)["status"] == "finished"


def test_the_polled_run_is_the_one_that_was_accepted(monkeypatch, tmp_path) -> None:
    """The id in the 202 is the id the history answers to, or the page follows nothing."""
    stub_the_audit(monkeypatch, tmp_path)
    client, _ = client_over(tmp_path)
    run_id = accepted_run_id(client)
    assert poll_until_terminal(client, run_id)["run_id"] == run_id


# --- an id no run has ----------------------------------------------------------

@pytest.mark.parametrize("malformed", MALFORMED_IDS)
def test_a_run_id_that_is_not_32_lowercase_hex_is_a_404(tmp_path, malformed) -> None:
    """Not a 500 and not a filesystem join: the shape is checked before the store."""
    client, _ = client_over(tmp_path)
    assert client.get(f"{RUNS}/{malformed}").status_code == NO_SUCH_RUN


@pytest.mark.parametrize("malformed", MALFORMED_IDS)
def test_a_malformed_run_id_never_reaches_the_store(tmp_path, malformed) -> None:
    """Where the shape check acts: a request-supplied string that is not a run id stops here."""
    client, double = client_over_a_recording_store(tmp_path)
    assert client.get(f"{RUNS}/{malformed}").status_code == NO_SUCH_RUN
    assert double.asked == []


def test_a_well_formed_id_does_reach_the_store(tmp_path) -> None:
    """Non-vacuity: the store above was reachable, and was simply never asked."""
    client, double = client_over_a_recording_store(tmp_path)
    client.get(f"{RUNS}/{UNUSED_ID}")
    assert double.asked == [UNUSED_ID]


def test_a_well_formed_id_no_row_carries_is_also_a_404(tmp_path) -> None:
    """The other half: the shape check is not the only reason a run is not found."""
    client, _ = client_over(tmp_path)
    assert client.get(f"{RUNS}/{UNUSED_ID}").status_code == NO_SUCH_RUN


def test_the_404_says_what_it_could_not_find(tmp_path) -> None:
    """Both cases say the same true thing, so neither leaks which one it was."""
    client, _ = client_over(tmp_path)
    assert client.get(f"{RUNS}/{UNUSED_ID}").json()["detail"] == "no run has that id"


def test_a_stored_run_is_answered_with_200(tmp_path) -> None:
    """Non-vacuity: the 404s above are about the id, not about the route being broken."""
    client, registry = client_over(tmp_path)
    registry.store.save(a_stored_run(UNUSED_ID))
    assert client.get(f"{RUNS}/{UNUSED_ID}").status_code == OK


# --- the list ------------------------------------------------------------------

def test_the_list_carries_the_three_documented_keys(tmp_path) -> None:
    """`{schema_version, stored_run_count, runs}`, and an empty history is not an error."""
    client, _ = client_over(tmp_path)
    body = client.get(RUNS).json()
    assert set(body) == LIST_KEYS
    assert body["runs"] == []


def test_a_list_row_is_the_summary_form(tmp_path) -> None:
    """`result` holds two whole artifacts; fifty of them in one reply is not a view."""
    client, registry = client_over(tmp_path)
    registry.store.save(a_stored_run(UNUSED_ID))
    row = client.get(RUNS).json()["runs"][0]
    assert DROPPED_FROM_A_ROW.isdisjoint(row)
    assert row["run_id"] == UNUSED_ID


def test_a_list_row_carries_the_repository_key_the_page_groups_on(tmp_path) -> None:
    """Served rather than re-derived: the page groups on this and owns no copy of the rule.

    Computed per request from `repo_url`, so the value is the same one
    `pipeline._reused` joins on. `test_canonical_repo_url.py` holds what it must
    equal; this holds that a list row carries it at all, which is the only place
    the page reads it.
    """
    client, registry = client_over(tmp_path)
    registry.store.save(a_stored_run(UNUSED_ID))
    row = client.get(RUNS).json()["runs"][0]
    assert row["canonical_repo_url"] == canonical_url(URL)


def test_a_list_row_names_who_asked_for_the_run(tmp_path) -> None:
    """The history list is where the name is read, so it survives the summary that builds it."""
    client, registry = client_over(tmp_path)
    registry.store.save(a_stored_run(UNUSED_ID))
    assert client.get(RUNS).json()["runs"][0]["auditor"] == AUDITOR


def test_the_stored_count_is_the_whole_history_and_the_list_is_capped(tmp_path) -> None:
    """The pair a reader compares to learn the history is longer than the page shows."""
    client, registry = client_over(tmp_path)
    for index in range(STORED_OVER_THE_CAP):
        registry.store.save(a_stored_run(f"{index:032x}"))
    body = client.get(RUNS).json()
    assert body["stored_run_count"] == STORED_OVER_THE_CAP
    assert len(body["runs"]) == HISTORY_LIST_LIMIT


def test_the_list_is_newest_first(tmp_path) -> None:
    """What the history page shows, in the order it shows it."""
    client, registry = client_over(tmp_path)
    registry.store.save(replace(a_stored_run("a" * 32), started_at="2026-09-09T10:00:00+00:00"))
    registry.store.save(a_stored_run("b" * 32))
    assert [row["run_id"] for row in client.get(RUNS).json()["runs"]] == ["b" * 32, "a" * 32]
