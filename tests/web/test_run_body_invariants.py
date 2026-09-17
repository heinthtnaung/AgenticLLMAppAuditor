"""The invariants `docs/SCHEMAS.md` states about a run body, over bodies the routes built.

The document lists them as testable, so they are tested: each one below is one
sentence from "The run record", asserted on a body the routes actually built
rather than on a record constructed in memory. Three of them are already
enforced twice -- by `RunRecord.__post_init__` and by the table's `CHECK`
constraints -- and both of those are held elsewhere; what this file adds is the
*served* body, which is where a page reads them and where a computed field could
contradict a stored one.

The last two invariants are about the two fields computed per request, and they
are `test_run_artifacts_flags.py`: `artifacts_dir` null implying
`artifacts_present` false cannot be asserted about a record at all, only about a
reply, so it needs a tree on disk and belongs with the rest of that subject.

The whole file skips without the server packages: these are properties of a
reply, and with no fastapi there is nothing to reply.
"""

import json

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from pathlib import Path                           # noqa: E402

from outputs import FINDINGS_NAME                  # noqa: E402
from run_record import (                           # noqa: E402
    FAILED, FINISHED, REPLY_SCHEMA_VERSION, RUNNING)

from .api_stubs import (                          # noqa: E402
    accepted_run_id, audit_and_poll, client_over, read_run)
from .audit_stub import (                          # noqa: E402
    artifacts_dir_for, hold_the_audit, stub_the_audit, wait_for_the_worker)

FINDING_COUNT = 4

TOOL_MESSAGE = "the repository could not be reached"


def plant_findings(tmp_path: Path) -> Path:
    """Write the one artifact these bodies read a count and a download off."""
    written = artifacts_dir_for(tmp_path)
    written.mkdir(parents=True)
    (written / FINDINGS_NAME).write_text(
        json.dumps({"schema_version": 7, "finding_count": FINDING_COUNT,
                    "findings": [], "coverage": {}}), encoding="utf-8")
    return written


# --- finished iff result -------------------------------------------------------

def test_a_finished_run_carries_a_result(monkeypatch, tmp_path) -> None:
    """`status == finished` iff `result` is non-null, in the direction a page renders."""
    stub_the_audit(monkeypatch, tmp_path)
    client, _ = client_over(tmp_path)
    body = audit_and_poll(client)
    assert body["status"] == FINISHED
    assert body["result"] is not None


def test_a_run_still_going_carries_no_result(monkeypatch, tmp_path) -> None:
    """The other direction: `null` means the run has not finished, not "no findings"."""
    let_it_finish = hold_the_audit(monkeypatch, tmp_path)
    client, registry = client_over(tmp_path)
    try:
        body = read_run(client, accepted_run_id(client))
        assert body["status"] == RUNNING
        assert body["result"] is None
    finally:
        let_it_finish.set()
        wait_for_the_worker(registry)


def test_a_failed_run_carries_no_result(monkeypatch, tmp_path) -> None:
    """A failure has nothing to show, and `null` is how the page is told so."""
    stub_the_audit(monkeypatch, tmp_path, error=ValueError(TOOL_MESSAGE))
    client, _ = client_over(tmp_path)
    body = audit_and_poll(client)
    assert body["status"] == FAILED
    assert body["result"] is None


# --- failed iff error ----------------------------------------------------------

def test_a_failed_run_carries_the_tools_own_sentence(monkeypatch, tmp_path) -> None:
    """`status == failed` iff `error`: the message the command line would have printed."""
    stub_the_audit(monkeypatch, tmp_path, error=ValueError(TOOL_MESSAGE))
    client, _ = client_over(tmp_path)
    assert audit_and_poll(client)["error"] == TOOL_MESSAGE


def test_a_finished_run_carries_no_error(monkeypatch, tmp_path) -> None:
    """The other direction, which a page shows as a red panel if it is wrong."""
    stub_the_audit(monkeypatch, tmp_path)
    client, _ = client_over(tmp_path)
    assert audit_and_poll(client)["error"] is None


# --- running iff no finish time iff no duration --------------------------------

def test_a_run_still_going_has_neither_a_finish_time_nor_a_duration(monkeypatch,
                                                                    tmp_path) -> None:
    """Both null, and never "finished at an unknown time" or a duration so far."""
    let_it_finish = hold_the_audit(monkeypatch, tmp_path)
    client, registry = client_over(tmp_path)
    try:
        body = read_run(client, accepted_run_id(client))
        assert (body["status"], body["finished_at"], body["seconds"]) == (RUNNING, None, None)
    finally:
        let_it_finish.set()
        wait_for_the_worker(registry)


def test_a_terminal_run_has_both(monkeypatch, tmp_path) -> None:
    """The converse, and `seconds` is the whole job rather than `result.seconds`."""
    stub_the_audit(monkeypatch, tmp_path)
    client, _ = client_over(tmp_path)
    body = audit_and_poll(client)
    assert body["finished_at"] is not None
    assert body["seconds"] >= 0


# --- the two versions agree ----------------------------------------------------

def test_the_body_and_its_result_carry_the_same_version(monkeypatch, tmp_path) -> None:
    """Equal by construction: one constant for everything under `/api/`."""
    stub_the_audit(monkeypatch, tmp_path)
    client, _ = client_over(tmp_path)
    body = audit_and_poll(client)
    assert body["schema_version"] == body["result"]["schema_version"] == REPLY_SCHEMA_VERSION


# --- a count with a document behind it -----------------------------------------

def test_a_finding_count_matches_the_document_it_was_copied_from(monkeypatch,
                                                                 tmp_path) -> None:
    """Copied from `findings.json`'s own count, so the two can never disagree."""
    stub_the_audit(monkeypatch, tmp_path)
    plant_findings(tmp_path)
    client, _ = client_over(tmp_path)
    body = audit_and_poll(client)
    assert body["finding_count"] == FINDING_COUNT
    assert body["result"]["findings"]["finding_count"] == FINDING_COUNT


def test_a_run_that_wrote_no_findings_document_carries_no_count(monkeypatch,
                                                                tmp_path) -> None:
    """`null` is not `0`: no document stands behind it, which is a gap and not a result."""
    stub_the_audit(monkeypatch, tmp_path)
    client, _ = client_over(tmp_path)
    body = audit_and_poll(client)
    assert body["finding_count"] is None
    assert body["result"]["findings"] is None
