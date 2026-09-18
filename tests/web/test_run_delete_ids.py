"""Which ids `DELETE /api/runs/{run_id}` accepts, and where the ones it refuses stop.

Split from `test_run_delete.py`, which holds which *statuses* may be forgotten.
Two questions, and this is the one about the string in the path.

**A malformed id is a 404, not a 500.** "No run has that id" is true of `../..`
as much as of an id nobody used, and checking the shape keeps a request-supplied
string out of a filesystem join -- `web/downloads.py` builds a path from the
directory an id chooses.

**And the status code alone cannot see that guard**, which is the whole reason
this file exists rather than four lines in the other one: with the shape check
deleted the store is simply asked for `../..`, finds nothing, and the route
answers the same 404. So it is measured where it acts, against
`api_stubs.StoreThatRecordsLookups`, which records every id it was handed. On a
*delete* that guard is worth more than on a read, because the id chooses a row
that is about to be destroyed.

`MALFORMED_IDS` is shared with `test_run_routes.py`, which makes the same
measurement of the same `RUN_ID` pattern on the GET. One list, because two
routes apply one pattern and a list that grew in one file would quietly leave
the other testing less than it claims.

Runs are written straight to the store rather than audited. Every application is
a fresh one over a store under `tmp_path`; see `api_stubs.py`. The whole file
skips without the server packages, because there is no endpoint without them.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from .api_stubs import (                           # noqa: E402
    MALFORMED_IDS, RUNS, client_over, client_over_a_recording_store)
from .run_rows import ENVELOPE, failed, finished, running   # noqa: E402

NO_SUCH_RUN = 404

# One id per status, so the store the route reaches really holds rows.
FAILED_ID = "a" * 32
FINISHED_ID = "b" * 32
RUNNING_ID = "c" * 32

# A well-formed id nobody stored: the 404 below is about the row, not the shape.
UNUSED_ID = "0" * 32


def client_holding_all_three(tmp_path):
    """A client over a history with one failed, one finished and one running row."""
    client, registry = client_over(tmp_path)
    registry.store.save(failed(FAILED_ID))
    registry.store.save(finished(FINISHED_ID), ENVELOPE)
    registry.store.save(running(RUNNING_ID))
    return client, registry


# --- an id no run has -----------------------------------------------------------

def test_an_id_no_row_carries_is_a_404(tmp_path) -> None:
    """The same answer the GET gives, and for the same reason."""
    client, _ = client_holding_all_three(tmp_path)
    response = client.delete(f"{RUNS}/{UNUSED_ID}")
    assert response.status_code == NO_SUCH_RUN
    assert response.json()["detail"] == "no run has that id"


@pytest.mark.parametrize("malformed", MALFORMED_IDS)
def test_a_malformed_id_is_a_404_and_not_a_500(tmp_path, malformed) -> None:
    """"No run has that id" is true of `../..` as much as of an id nobody used."""
    client, _ = client_holding_all_three(tmp_path)
    assert client.delete(f"{RUNS}/{malformed}").status_code == NO_SUCH_RUN


@pytest.mark.parametrize("malformed", MALFORMED_IDS)
def test_a_malformed_id_never_reaches_the_store(tmp_path, malformed) -> None:
    """Where the shape check acts. On a delete, the id chooses a row about to be destroyed."""
    client, double = client_over_a_recording_store(tmp_path)
    assert client.delete(f"{RUNS}/{malformed}").status_code == NO_SUCH_RUN
    assert double.asked == []


def test_a_well_formed_id_does_reach_the_store(tmp_path) -> None:
    """Non-vacuity: the double above was reachable, and was simply never asked."""
    client, double = client_over_a_recording_store(tmp_path)
    client.delete(f"{RUNS}/{UNUSED_ID}")
    assert double.asked == [UNUSED_ID]


def test_an_id_that_carries_no_row_is_never_deleted(tmp_path) -> None:
    """The route reads the row first, so a miss is a 404 before anything is removed."""
    client, double = client_over_a_recording_store(tmp_path)
    client.delete(f"{RUNS}/{UNUSED_ID}")
    assert double.deleted == []


