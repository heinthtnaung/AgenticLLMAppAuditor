"""The emitter's pure parts: the product, the pinned instant, the id and the flags.

None of these launches anything. They are the decisions taken before vexctl is
called, and each one is a way the document could be wrong while still parsing:
an unpinned instant, an id that differs between two runs of the same input, a
product that names nothing, or a flag OpenVEX allows only for `not_affected`.
"""

import json
from pathlib import Path

import pytest

import emit_vex
from advisory_fixtures import ADVISORY_PURL, DB_UPDATED_AT
from artifacts.vex import AFFECTED, NO_FIX, pinned_epoch
from emit_vex import document_id, product_iri
from grading_keys import MANIFEST_SUFFIX
from vex_fixtures import PINNED_EPOCH, PRODUCT

# A real Trivy database date, with the nine fractional digits Go writes and
# `datetime.fromisoformat` will not read.
NANOSECOND_DATE = "2026-09-01T06:57:09.526069867Z"
NANOSECOND_EPOCH = "1788245829"

# The epoch of advisory_fixtures' own date (2026-02-01T06:00:00Z), written down
# rather than derived, so the conversion is checked against a value and not itself.

# Computed once from (PRODUCT, PINNED_EPOCH) and written down, so a salted or
# clock-dependent id fails here instead of shipping two ids for one document.
EXPECTED_ID = ("https://openvex.dev/docs/public/agentic-llm-app-auditor-"
               "69fa623b6e8bb25e22ee36291664ffb8")

APP = "an-audited-app"
UPSTREAM_URL = "https://example.com/an-audited-app"
UPSTREAM_COMMIT = "0123456789abcdef"
FETCHED_COMMIT = "fedcba9876543210"

STATEMENT = {
    "vulnerability": "CVE-2024-0001",
    "subcomponent": ADVISORY_PURL,
    "status": AFFECTED,
    "status_note": "Reached by ShellTool at app/agent.py:12",
    "action_statement": NO_FIX,
}

# Allowed by OpenVEX only beside `not_affected`, which this project cannot state.
FORBIDDEN_FLAGS = ("--justification", "--impact-statement")


def write_pin(directory: Path, app: str, commit: str) -> None:
    """Write one manifest recording where an app came from and the commit it was at."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{app}{MANIFEST_SUFFIX}").write_text(
        json.dumps({"upstream_url": UPSTREAM_URL, "upstream_commit": commit}),
        encoding="utf-8")


def place_roots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    """Point both pin locations at a temporary tree, so no test reads the real ones."""
    keys, fetched = tmp_path / "grading_keys", tmp_path / "fetched"
    monkeypatch.setattr(emit_vex, "key_path",
                        lambda app, suffix: keys / f"{app}{suffix}")
    monkeypatch.setattr(emit_vex, "FETCH_ROOT", fetched)
    return keys, fetched


def test_a_nanosecond_database_date_becomes_epoch_seconds() -> None:
    """Trivy writes nine fractional digits; the stdlib reads six, so they are trimmed."""
    assert pinned_epoch({"advisory_db_updated_at": NANOSECOND_DATE}) == NANOSECOND_EPOCH


def test_a_whole_second_database_date_needs_no_trimming() -> None:
    """The other shape a pin arrives in, so the trimming is not the only path."""
    assert pinned_epoch({"advisory_db_updated_at": DB_UPDATED_AT}) == PINNED_EPOCH


def test_an_audit_that_read_no_advisory_data_cannot_be_pinned() -> None:
    """No date is no fact to state, and the message says how to get one."""
    with pytest.raises(ValueError) as raised:
        pinned_epoch({"advisory_db_updated_at": None})
    assert "no advisory data" in str(raised.value)


def test_the_same_product_and_instant_give_the_same_id() -> None:
    """Two runs over one audit must not produce two documents."""
    assert document_id(PRODUCT, PINNED_EPOCH) == document_id(PRODUCT, PINNED_EPOCH)


def test_the_id_is_the_one_written_down_for_this_input() -> None:
    """Against a fixed expected value: Python's hash() is salted per process, sha256 is not."""
    assert document_id(PRODUCT, PINNED_EPOCH) == EXPECTED_ID


def test_a_different_product_gets_a_different_id() -> None:
    """Two apps assessed against one database snapshot are two documents."""
    assert document_id("https://example.com/other@0123456789abcdef",
                       PINNED_EPOCH) != EXPECTED_ID


def test_a_different_snapshot_gets_a_different_id() -> None:
    """One app re-assessed against newer advisory data is a new document, not an edit."""
    assert document_id(PRODUCT, NANOSECOND_EPOCH) != EXPECTED_ID


def test_the_product_is_read_from_the_grading_keys_pin(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A graded app's manifest says where it came from, so the IRI needs no argument."""
    keys, _ = place_roots(monkeypatch, tmp_path)
    write_pin(keys, APP, UPSTREAM_COMMIT)
    assert product_iri(APP) == f"{UPSTREAM_URL}@{UPSTREAM_COMMIT}"


def test_the_product_is_read_from_a_fetched_tree_s_pin(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """An app fetched by URL is pinned too, and has no grading key beside it."""
    _, fetched = place_roots(monkeypatch, tmp_path)
    write_pin(fetched, APP, FETCHED_COMMIT)
    assert product_iri(APP) == f"{UPSTREAM_URL}@{FETCHED_COMMIT}"


def test_the_grading_keys_pin_is_preferred_over_a_fetched_one(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Both can exist; the hand-signed-off one is what the evaluation grades."""
    keys, fetched = place_roots(monkeypatch, tmp_path)
    write_pin(keys, APP, UPSTREAM_COMMIT)
    write_pin(fetched, APP, FETCHED_COMMIT)
    assert product_iri(APP) == f"{UPSTREAM_URL}@{UPSTREAM_COMMIT}"


def test_an_unpinned_app_is_refused_and_the_flag_is_named(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A statement is about a product, so guessing one would be inventing the claim."""
    place_roots(monkeypatch, tmp_path)
    with pytest.raises(FileNotFoundError) as raised:
        product_iri(APP)
    assert "--product" in str(raised.value)
    assert APP in str(raised.value)


def test_the_flags_carry_the_whole_statement() -> None:
    """Each flag is checked against the value after it, so a shifted list cannot pass."""
    arguments = emit_vex._statement_arguments(STATEMENT, PRODUCT)
    paired = dict(zip(arguments[::2], arguments[1::2]))
    assert paired["--product"] == PRODUCT
    assert paired["--subcomponents"] == ADVISORY_PURL
    assert paired["--vuln"] == STATEMENT["vulnerability"]
    assert paired["--status"] == AFFECTED
    assert paired["--status-note"] == STATEMENT["status_note"]
    assert paired["--action-statement"] == NO_FIX


def test_the_flags_never_include_a_not_affected_only_field() -> None:
    """OpenVEX allows these two only beside `not_affected`, which the mapping cannot support."""
    arguments = emit_vex._statement_arguments(STATEMENT, PRODUCT)
    for flag in FORBIDDEN_FLAGS:
        assert flag not in arguments
