"""The background job: what it stores as it goes, how it ends, and the slot it holds.

The registry is driven directly here, with no HTTP at all. `web/run_jobs.py` is
free of fastapi like the record and the store beside it, so the part of the
wrapper that owns a thread and a mutual exclusion is testable on a clean
checkout -- and a test that posts a request cannot say which of the two layers
released the slot.

**The store is the only state**, which is the obligation the background thread
brought with it: every stage the audit announces is written there, so a poll
reads what the worker wrote and not a second copy in memory. One test below
reads the store from *inside* the audit to say so.

The single slot is `test_run_slot.py`: mutual exclusion and the regression that
used to wedge it are one subject, and this file is another.

`main.run` is replaced throughout. What is under test is the wrapper's handling
of an outcome; the audit itself is driven end to end in `test_api_audit.py`.
"""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from audit_request import AuditRequest
import main
from outputs import FINDINGS_NAME, SURFACES_NAME
from run_jobs import Registry
from run_record import FAILED, FINISHED, REPLY_SCHEMA_VERSION, RUNNING, RunRecord

from .audit_stub import (
    AUDITOR,    APP, RUN_SECONDS, URL, UNEXPECTED_ERROR, artifacts_dir_for, open_a_store,
    repositories, stub_the_audit, wait_for_the_worker)

# Three boundaries in the order `progress.STAGES` puts them, so "announcement
# order" has something to be wrong about.
ANNOUNCED = ("fetch", "surfaces", "checks")

# What the planted documents declare. Different numbers, so a run that reported
# one of them twice would be caught.
FINDING_COUNT = 4
SURFACE_COUNT = 7

# The eight keys of the result envelope, which is `docs/SCHEMAS.md`'s "a view,
# not an artifact" and is stored whole. `comparison` is the eighth and is null
# on every path but `--compare-models`.
ENVELOPE_KEYS = {"schema_version", "app", "artifacts_dir", "seconds",
                 "advisories_read", "findings", "surfaces", "comparison"}

# The sentence a refusal carries. `ValueError` is one of `main.EXPECTED_FAILURES`,
# so this is the tool's own message reaching the page rather than a traceback.
TOOL_MESSAGE = "fetched/demo-app holds another repository; remove it to fetch this one"


def a_registry(tmp_path: Path) -> Registry:
    """A registry over a fresh store, which is all `api.py` builds."""
    return Registry(open_a_store(tmp_path))


def a_request(**options) -> AuditRequest:
    """One audit the page asked for. The name is not part of it and is passed beside it."""
    return AuditRequest(url=URL, **options)


def run_to_completion(registry: Registry, **options) -> tuple[RunRecord, dict | None]:
    """Start one audit, wait for the worker, and read back what it stored."""
    accepted = registry.start(a_request(**options), AUDITOR)
    wait_for_the_worker(registry)
    stored = registry.store.get(accepted.run_id)
    assert stored is not None, "the registry accepted a run it did not store"
    return stored


def plant_documents(tmp_path: Path) -> None:
    """Write the two artifacts a finished audit reads its counts off."""
    written = artifacts_dir_for(tmp_path)
    written.mkdir(parents=True)
    (written / FINDINGS_NAME).write_text(
        json.dumps({"schema_version": 7, "finding_count": FINDING_COUNT, "findings": []}),
        encoding="utf-8")
    (written / SURFACES_NAME).write_text(
        json.dumps({"schema_version": 3, "surface_count": SURFACE_COUNT, "surfaces": []}),
        encoding="utf-8")


# --- what acceptance stores ----------------------------------------------------

def test_an_accepted_run_is_stored_before_start_returns(monkeypatch, tmp_path) -> None:
    """The 202 is answered from a row, so a poll that arrives immediately finds one."""
    stub_the_audit(monkeypatch, tmp_path)
    registry = a_registry(tmp_path)
    accepted = registry.start(a_request(), AUDITOR)
    assert registry.store.get(accepted.run_id) is not None
    wait_for_the_worker(registry)


def test_the_stored_run_is_the_request_that_was_asked_for(monkeypatch, tmp_path) -> None:
    """`options` must round-trip exactly, so a re-run is the same run."""
    stub_the_audit(monkeypatch, tmp_path)
    asked = a_request(semantic_probe=True)
    record, _ = run_to_completion(a_registry(tmp_path), semantic_probe=True)
    assert record.repo_url == URL
    assert record.options == asdict(asked)


def test_the_name_lands_on_the_record_and_not_in_the_options(monkeypatch,
                                                              tmp_path) -> None:
    """Why `start` takes it as a second argument: the two are different facts.

    `options` is `asdict(asked)` and a re-run is built from it, so a name in
    there would re-run the audit as someone else. The record is where
    who-and-when belongs.
    """
    stub_the_audit(monkeypatch, tmp_path)
    record, _ = run_to_completion(a_registry(tmp_path))
    assert record.auditor == AUDITOR
    assert "auditor" not in record.options


def test_the_stored_name_is_the_stripped_one(monkeypatch, tmp_path) -> None:
    """A browser field arrives padded, and the record stores the name rather than the padding.

    This was the divergence: the record stripped and `options["auditor"]` did
    not, so one run carried two spellings of one answer.
    """
    stub_the_audit(monkeypatch, tmp_path)
    registry = a_registry(tmp_path)
    accepted = registry.start(a_request(), f"  {AUDITOR}  ")
    wait_for_the_worker(registry)
    assert accepted.auditor == AUDITOR


def test_the_audit_was_asked_for_the_repository_the_request_named(monkeypatch,
                                                                  tmp_path) -> None:
    """Non-vacuity for every status below: the command line really named this URL."""
    parsed = stub_the_audit(monkeypatch, tmp_path)
    run_to_completion(a_registry(tmp_path))
    assert repositories(parsed) == [URL]


# --- the stages ----------------------------------------------------------------

def test_the_stages_are_stored_in_the_order_they_were_announced(monkeypatch,
                                                                tmp_path) -> None:
    """`stages`' order is its entire content: it is what has happened, in sequence."""
    stub_the_audit(monkeypatch, tmp_path, announces=ANNOUNCED)
    record, _ = run_to_completion(a_registry(tmp_path))
    assert record.stages == list(ANNOUNCED)


def test_a_run_that_announced_nothing_stores_an_empty_list(monkeypatch, tmp_path) -> None:
    """`[]` means nothing has been announced yet, which is not "no stages ran"."""
    stub_the_audit(monkeypatch, tmp_path)
    record, _ = run_to_completion(a_registry(tmp_path))
    assert record.stages == []


def test_a_stage_is_readable_from_the_store_while_the_run_is_still_going(monkeypatch,
                                                                        tmp_path) -> None:
    """The store is the only state, so a poll mid-run reads the worker's own writes."""
    seen: list = []
    registry = a_registry(tmp_path)

    def fake_run(args: argparse.Namespace, on_stage=None) -> dict:
        """Announce one stage, then read the run back the way a poll would."""
        on_stage(ANNOUNCED[0], "")
        record, _ = registry.store.get(registry.active_run_id())
        seen.append((record.status, list(record.stages)))
        # `comparison` is present because every path through the real `main.run`
        # sets it. `run_jobs` subscripts the key rather than `.get()`-ing it, so
        # that a missing one is a failure here and not a silent "one arm ran".
        return {"app": APP, "artifacts": artifacts_dir_for(tmp_path),
                "seconds": RUN_SECONDS, "advisories_read": False,
                "comparison": None}

    monkeypatch.setattr(main, "run", fake_run)
    registry.start(a_request(), AUDITOR)
    wait_for_the_worker(registry)
    assert seen == [(RUNNING, [ANNOUNCED[0]])]


# --- how a run ends ------------------------------------------------------------

def test_a_finished_run_reads_its_counts_off_the_documents(monkeypatch, tmp_path) -> None:
    """Copied from each document's own count, never recounted by the wrapper."""
    stub_the_audit(monkeypatch, tmp_path)
    plant_documents(tmp_path)
    record, _ = run_to_completion(a_registry(tmp_path))
    assert (record.status, record.finding_count, record.surface_count) == (
        FINISHED, FINDING_COUNT, SURFACE_COUNT)


def test_a_finished_run_that_wrote_no_documents_carries_no_counts(monkeypatch,
                                                                  tmp_path) -> None:
    """`null`, not `0`: a count with no document behind it is what this project refuses."""
    stub_the_audit(monkeypatch, tmp_path)
    record, _ = run_to_completion(a_registry(tmp_path))
    assert record.status == FINISHED
    assert (record.finding_count, record.surface_count) == (None, None)


def test_a_finished_run_stores_the_documented_envelope(monkeypatch, tmp_path) -> None:
    """Eight keys, kept so a past run stays viewable after `artifacts/` is cleaned."""
    stub_the_audit(monkeypatch, tmp_path)
    plant_documents(tmp_path)
    _, envelope = run_to_completion(a_registry(tmp_path))
    assert set(envelope) == ENVELOPE_KEYS
    assert envelope["schema_version"] == REPLY_SCHEMA_VERSION
    assert envelope["findings"]["finding_count"] == FINDING_COUNT


def test_the_envelope_names_the_app_and_where_it_wrote(monkeypatch, tmp_path) -> None:
    """Read back from the run, never re-derived from the URL's last segment."""
    stub_the_audit(monkeypatch, tmp_path)
    _, envelope = run_to_completion(a_registry(tmp_path))
    assert envelope["app"] == APP
    assert envelope["artifacts_dir"] == str(artifacts_dir_for(tmp_path))
    assert envelope["seconds"] == RUN_SECONDS


def test_a_refusal_the_tool_expects_becomes_a_failed_run(monkeypatch, tmp_path) -> None:
    """A tool refusal is no longer a status code: it lands as `failed` and an error."""
    stub_the_audit(monkeypatch, tmp_path, error=ValueError(TOOL_MESSAGE))
    record, envelope = run_to_completion(a_registry(tmp_path))
    assert record.status == FAILED
    assert record.error == TOOL_MESSAGE
    assert envelope is None


def test_an_unexpected_failure_becomes_a_failed_run_naming_its_class(monkeypatch,
                                                                     tmp_path) -> None:
    """A worker that died would leave the run saying `running` for ever; this names the bug."""
    stub_the_audit(monkeypatch, tmp_path, error=UNEXPECTED_ERROR("a bug, not a refusal"))
    record, _ = run_to_completion(a_registry(tmp_path))
    assert record.status == FAILED
    assert UNEXPECTED_ERROR.__name__ in record.error


def test_a_result_with_no_comparison_key_is_a_defect_and_not_one_arm(monkeypatch,
                                                                     tmp_path) -> None:
    """`produced["comparison"]`, not `.get()`: `None` may mean one thing only.

    `.get()` made a missing key and a null value the same answer, so a producer
    that stopped setting it would have read as "one arm ran" for ever -- a gap
    rendered as a result, on the one key whose whole job is to be `null` when a
    second arm did not run. `main.run` sets it on both branches, which
    `tests/compare/test_compare_run_result.py` holds; a result that does not is
    a defect, and the honest outcome is a failed run naming the exception.
    """
    def fake_run(args: argparse.Namespace, on_stage=None) -> dict:
        """Answer the way a producer that dropped the key would."""
        return {"app": APP, "artifacts": artifacts_dir_for(tmp_path),
                "seconds": RUN_SECONDS, "advisories_read": False}

    monkeypatch.setattr(main, "run", fake_run)
    record, envelope = run_to_completion(a_registry(tmp_path))
    assert record.status == FAILED
    assert KeyError.__name__ in record.error
    assert envelope is None


def test_a_result_that_carries_a_null_comparison_finishes(monkeypatch, tmp_path) -> None:
    """Non-vacuity for the test above: the key being `None` is the ordinary single-arm run."""
    stub_the_audit(monkeypatch, tmp_path)
    record, envelope = run_to_completion(a_registry(tmp_path))
    assert record.status == FINISHED
    assert envelope["comparison"] is None


def test_a_failed_run_still_stores_the_stages_it_reached(monkeypatch, tmp_path) -> None:
    """How far it got is the useful half of a failure, so it is kept rather than dropped."""
    stub_the_audit(monkeypatch, tmp_path, error=ValueError(TOOL_MESSAGE),
                   announces=ANNOUNCED[:2])
    record, _ = run_to_completion(a_registry(tmp_path))
    assert record.stages == list(ANNOUNCED[:2])
