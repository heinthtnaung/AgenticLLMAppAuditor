"""One run's shape: what it refuses to be, and the two bodies it is served as.

`RunRecord` is the wire and the row at once, so three readers agree about it or
none of them does. This file holds the record's own refusals and the two body
forms built from it; the `CHECK` constraints that refuse the same three
combinations a second time are `test_history_rows.py`, and the trip through
SQLite text is `test_run_record_columns.py`.

No fastapi here: `run_record.py` and `history_store.py` are both free of it on
purpose, so this file runs on a clean checkout with no web extra installed.
"""

from dataclasses import replace

import pytest

import run_record
from run_record import (
    COMPUTED_FIELDS, DURABLE_FIELDS, REPLY_SCHEMA_VERSION, RUN_STATUSES,
    RunRecord, body, started, summary)

# The version everything under `/api/` carries, pinned as a literal beside the
# constant it must equal. Imported alone it would agree with itself.
EXPECTED_REPLY_SCHEMA_VERSION = 2

# The closed vocabulary, spelled out. Three values and not four: `cancelled`
# lands with a cancel endpoint, not before one.
EXPECTED_STATUSES = ("running", "finished", "failed")

# A status no producer writes, to show the refusal is a membership test.
UNKNOWN_STATUS = "cancelled"

URL = "https://example.invalid/owner/demo-app"
OPTIONS = {"url": URL, "semantic_probe": True, "draft_key": False,
           "compare_models": False, "cloud_model": ""}

# Two announced stages, in order, because the order is the whole content.
STAGES = ["fetch", "surfaces"]

WHEN = "2026-09-09T12:00:00+00:00"
SECONDS = 1.5

# What the summary form drops, and nothing else.
SUMMARY_DROPS = {"result", "schema_version"}

# A stored envelope, cut down to the one key a round trip has to preserve.
ENVELOPE_TEXT = {"schema_version": REPLY_SCHEMA_VERSION, "app": "demo-app"}

RUN_ID_LENGTH = 32


def a_running_record() -> RunRecord:
    """One accepted run, with nothing established yet."""
    return RunRecord(run_id="a" * RUN_ID_LENGTH, repo_url=URL,
                     options=dict(OPTIONS), started_at=WHEN)


def a_finished_record() -> RunRecord:
    """The same run, having got all the way through."""
    return replace(a_running_record(), status="finished", finished_at=WHEN,
                   seconds=SECONDS, stages=list(STAGES), app="demo-app",
                   artifacts_dir="artifacts/agentic_auditor/demo-app",
                   finding_count=3, surface_count=6)


# --- the vocabulary -----------------------------------------------------------

def test_the_reply_version_is_the_one_the_page_is_built_against() -> None:
    """The page ships separately in `frontend/dist/`, so this number is the handshake."""
    assert REPLY_SCHEMA_VERSION == EXPECTED_REPLY_SCHEMA_VERSION


def test_the_statuses_are_the_three_documented_ones() -> None:
    """A fourth value is a branch every reader carries for ever; there are three."""
    assert RUN_STATUSES == EXPECTED_STATUSES


# --- what a record refuses to be ----------------------------------------------

def test_a_status_outside_the_vocabulary_is_refused() -> None:
    """`cancelled` is not a status, and a record that claimed it would render as one."""
    with pytest.raises(ValueError, match=UNKNOWN_STATUS):
        replace(a_running_record(), status=UNKNOWN_STATUS, finished_at=WHEN)


def test_a_failed_run_with_no_error_is_refused() -> None:
    """`status == failed` iff `error`: a failure with no sentence is a blank in the UI."""
    with pytest.raises(ValueError, match="failed run carries an error"):
        replace(a_running_record(), status="failed", finished_at=WHEN)


def test_an_error_on_a_run_that_did_not_fail_is_refused() -> None:
    """The other direction of the same iff, which a one-way check would let through."""
    with pytest.raises(ValueError, match="failed run carries an error"):
        replace(a_finished_record(), error="something went wrong")


def test_a_running_run_that_has_a_finish_time_is_refused() -> None:
    """`running` iff `finished_at is null`, or a page spins on a run that is over."""
    with pytest.raises(ValueError, match="finished_at exactly when"):
        replace(a_running_record(), finished_at=WHEN)


def test_a_terminal_run_with_no_finish_time_is_refused() -> None:
    """And its converse: "finished at an unknown time" is not a state this carries."""
    with pytest.raises(ValueError, match="finished_at exactly when"):
        replace(a_finished_record(), finished_at=None)


# --- what `started` establishes -----------------------------------------------

def test_an_accepted_run_is_running_and_knows_only_its_url() -> None:
    """The 202 body: everything not yet established is null, and `stages` is empty."""
    record = started(URL, OPTIONS)
    assert (record.status, record.repo_url, record.stages) == ("running", URL, [])
    assert (record.app, record.artifacts_dir, record.finding_count) == (None, None, None)


def test_an_accepted_run_carries_a_32_character_lowercase_hex_id() -> None:
    """`uuid4().hex`, which the routes then check a request-supplied id against."""
    run_id = started(URL, OPTIONS).run_id
    assert len(run_id) == RUN_ID_LENGTH
    assert set(run_id) <= set("0123456789abcdef")


def test_two_accepted_runs_do_not_share_an_id() -> None:
    """Non-vacuity for the id above: a constant would satisfy the shape check."""
    assert started(URL, OPTIONS).run_id != started(URL, OPTIONS).run_id


def test_the_options_are_copied_and_not_held() -> None:
    """A re-run must be exact, so the record may not alias the caller's dict."""
    asked = dict(OPTIONS)
    record = started(URL, asked)
    asked["semantic_probe"] = False
    assert record.options["semantic_probe"] is True


# --- the body and its summary form --------------------------------------------

def test_a_body_is_the_record_plus_the_version_the_computed_flags_and_the_result() -> None:
    """One parser for every single-run reply, so the key set is named rather than trusted."""
    full = body(a_running_record(), artifacts_present=False, artifacts_current=True)
    assert set(full) == {*DURABLE_FIELDS, *COMPUTED_FIELDS, "schema_version", "result"}


def test_a_summary_is_that_body_without_the_result_or_the_version() -> None:
    """The list's only variation from the detail, stated as exactly two dropped keys."""
    full = body(a_finished_record(), artifacts_present=True, artifacts_current=True,
                result=ENVELOPE_TEXT)
    assert set(full) - set(summary(full)) == SUMMARY_DROPS


def test_a_summary_keeps_every_other_field_the_detail_carries() -> None:
    """Derived from the body, so the list and the detail cannot describe a run differently."""
    full = body(a_finished_record(), artifacts_present=True, artifacts_current=False,
                result=ENVELOPE_TEXT)
    kept = summary(full)
    assert set(kept) == set(full) - SUMMARY_DROPS
    assert all(kept[key] == full[key] for key in kept)


def test_the_module_names_the_moment_it_writes_to_the_second() -> None:
    """`now()` is ISO 8601 UTC to the second: no microseconds to render, no local zone."""
    stamp = run_record.now()
    assert stamp.endswith("+00:00")
    assert "." not in stamp
