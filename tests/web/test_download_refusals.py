"""The four ways a run has no files to hand over, and the three endpoints that say so.

`web/downloads.py` resolves a directory once, in `_directory`, for the listing,
the archive and each named file. So each refusal is asserted on all three
endpoints rather than on whichever one it was written against: a guard that
moved into one handler would leave the other two serving.

The two that are worth stating as behaviour rather than as status codes:

- **A superseded run is refused with 409, not served.** Artifacts are keyed on
  the app name, not on the run, so a second audit of one URL writes over the
  first one's files. Serving them would put a newer run's bytes under an older
  run's timestamp -- honest refusal beats a quiet lie, and `docs/TODO.md`
  records that those files are simply not recoverable.
- **A run whose directory is gone is still readable.** `artifacts/` is
  disposable and the store is not: a finished run's findings live in the
  envelope, so the record answers 200 while its files answer 404. That pair is
  asserted in one test, because either half alone is the wrong behaviour.

The whole file skips without the server packages: with no fastapi there is
nothing to refuse.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from dataclasses import replace                    # noqa: E402
from pathlib import Path                           # noqa: E402

from run_record import FAILED                      # noqa: E402

from fastapi.testclient import TestClient          # noqa: E402

from .api_stubs import read_run                    # noqa: E402
from .audit_stub import artifacts_dir_for          # noqa: E402
from .download_fixtures import (                   # noqa: E402
    EARLY, ENVELOPE, LATER_RUN_ID, RUN_ID, SOME_NAMES, a_finished_row, a_run_holding)

DOWNLOAD = "/api/artifacts"
BUNDLE = "artifacts.zip"

OK = 200
NO_SUCH_RUN = 404
NOT_DOWNLOADABLE = 404
SUPERSEDED = 409

# A well-formed id nobody used, and one that is not a run id at all. Neither
# reaches a filesystem join: the directory comes from the stored row, never
# from the request.
UNUSED_ID = "0" * 32
NOT_A_RUN_ID = "../../etc"

TOOL_MESSAGE = "the repository could not be reached"


def a_run_whose_directory_is_gone(tmp_path: Path) -> TestClient:
    """A client on a finished run naming a directory that was never written."""
    client, registry, _ = a_run_holding(tmp_path, SOME_NAMES)
    gone = artifacts_dir_for(tmp_path) / "cleaned-away"
    registry.store.save(a_finished_row(RUN_ID, str(gone)), ENVELOPE)
    return client


def three_endpoints(run_id: str = RUN_ID) -> tuple[str, ...]:
    """Every path that resolves a run's directory before answering."""
    return (f"{DOWNLOAD}/{run_id}",
            f"{DOWNLOAD}/{run_id}/{BUNDLE}",
            f"{DOWNLOAD}/{run_id}/{SOME_NAMES[0]}")


# --- a run nobody stored -------------------------------------------------------

@pytest.mark.parametrize("path", three_endpoints(UNUSED_ID))
def test_an_id_no_run_carries_is_a_404(tmp_path, path) -> None:
    """The same sentence `GET /api/runs/{id}` gives, for the same reason."""
    client, _, _ = a_run_holding(tmp_path, SOME_NAMES)
    response = client.get(path)
    assert response.status_code == NO_SUCH_RUN
    assert response.json()["detail"] == "no run has that id"


@pytest.mark.parametrize("path", three_endpoints(NOT_A_RUN_ID))
def test_an_id_that_is_not_a_run_id_is_also_a_404(tmp_path, path) -> None:
    """No row has it, so no directory is chosen and nothing is joined onto a path."""
    client, _, _ = a_run_holding(tmp_path, SOME_NAMES)
    assert client.get(path).status_code == NO_SUCH_RUN


# --- a run that wrote nothing --------------------------------------------------

@pytest.mark.parametrize("path", three_endpoints())
def test_a_run_that_named_no_directory_is_refused(tmp_path, path) -> None:
    """A run that failed before it wrote has no directory, and its status says why."""
    client, registry, _ = a_run_holding(tmp_path, SOME_NAMES)
    registry.store.save(replace(a_finished_row(RUN_ID, None), status=FAILED,
                                error=TOOL_MESSAGE, finding_count=None,
                                surface_count=None), None)
    response = client.get(path)
    assert response.status_code == NOT_DOWNLOADABLE
    assert "its status says why" in response.json()["detail"]


# --- a run whose files are gone ------------------------------------------------

@pytest.mark.parametrize("path", three_endpoints())
def test_a_run_whose_directory_is_gone_is_refused(tmp_path, path) -> None:
    """`artifacts/` is disposable; the refusal names the directory that is not there."""
    response = a_run_whose_directory_is_gone(tmp_path).get(path)
    assert response.status_code == NOT_DOWNLOADABLE
    assert "is gone from disk" in response.json()["detail"]


def test_that_same_run_is_still_readable_from_the_store(tmp_path) -> None:
    """The pair: a row is never deleted for having lost its files, so the findings survive."""
    body = read_run(a_run_whose_directory_is_gone(tmp_path), RUN_ID)
    assert body["result"] == ENVELOPE
    assert body["artifacts_present"] is False


# --- a run a later one overwrote -----------------------------------------------

@pytest.mark.parametrize("path", three_endpoints())
def test_a_superseded_runs_files_are_refused_rather_than_served(tmp_path, path) -> None:
    """409: what is on disk is no longer what this run produced."""
    client, registry, directory = a_run_holding(tmp_path, SOME_NAMES)
    registry.store.save(a_finished_row(RUN_ID, str(directory), EARLY), ENVELOPE)
    registry.store.save(a_finished_row(LATER_RUN_ID, str(directory)), ENVELOPE)
    assert client.get(path).status_code == SUPERSEDED


def test_the_409_explains_that_artifacts_are_keyed_on_the_app(tmp_path) -> None:
    """A refusal a reader cannot act on is a bug report; this one says to audit again."""
    client, registry, directory = a_run_holding(tmp_path, SOME_NAMES)
    registry.store.save(a_finished_row(RUN_ID, str(directory), EARLY), ENVELOPE)
    registry.store.save(a_finished_row(LATER_RUN_ID, str(directory)), ENVELOPE)
    said = client.get(three_endpoints()[0]).json()["detail"]
    assert "keyed on the app name" in said
    assert "audit it again" in said


def test_the_later_runs_own_files_are_served(tmp_path) -> None:
    """Non-vacuity: the 409s above are about being superseded, not about the tree."""
    client, registry, directory = a_run_holding(tmp_path, SOME_NAMES)
    registry.store.save(a_finished_row(RUN_ID, str(directory), EARLY), ENVELOPE)
    registry.store.save(a_finished_row(LATER_RUN_ID, str(directory)), ENVELOPE)
    assert client.get(three_endpoints(LATER_RUN_ID)[0]).status_code == OK
