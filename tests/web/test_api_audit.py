"""One real audit through `POST /api/audit`, polled to a finish, and what comes out.

The endpoint is exercised over a repository this test writes into `tmp_path` --
the mixed Python/TypeScript app from `mixed_app_fixtures` -- with the clone, the
publish stage, the model, Syft and Trivy stubbed the way `cli_helpers` does. So
nothing here clones, launches a process, or waits on a server, and the audit
underneath is the real one: the counts asserted below are the ones the checks
actually produced, not a fixture's.

**The endpoint no longer blocks, so this file polls.** The POST answers 202 with
a run record and the audit runs on a background thread; every assertion about
what the audit produced is made against the record a poll returns once the run
reached a terminal status, which is exactly the sequence the page performs. The
old seven-key envelope is that record's `result`, non-null only once the run
finished.

What the synthetic tree costs is worth saying, because it is weaker than a real
repository: nothing here is oversized, non-UTF-8, malformed or shaped in a way
nobody foresaw, so a defect that only appears on an unforeseen repository is not
caught by this file.

Three things are held. The two documents in the reply are what the audit wrote
to disk -- `schema_version` included, because that field is the first casualty of
a wrapper that reshapes a contract for a browser. `artifacts_dir` names the
directory the audit really wrote into, so a page that tells someone where to
look is telling them the truth. And the record's counts are the documents' own,
so the history list and the dashboard cannot disagree about one run.

The staging is `real_audit_fixtures.py`, shared with
`test_auditor_not_in_artifacts.py`, which sweeps the files this run writes.

The whole file skips when the server packages are not installed: without
fastapi there is no endpoint to call. Everything the wrapper does that does not
need a server is tested in `test_audit_request.py`, `test_artifacts_read.py`,
`test_run_record.py` and `test_run_jobs.py`, which never skip.
"""

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from artifacts.finding import SCHEMA_VERSION as FINDINGS_SCHEMA_VERSION         # noqa: E402
from artifacts.surface import SCHEMA_VERSION as SURFACES_SCHEMA_VERSION         # noqa: E402
from checks.auditability import CHECK_NAME as AUDITABILITY_CHECK                # noqa: E402
from checks.output_handling import CHECK_NAME as QUERY_CHECK                    # noqa: E402
from checks.permissions import CHECK_NAME as PERMISSION_CHECK                   # noqa: E402
from checks.taint import CHECK_NAME as TAINT_CHECK                              # noqa: E402
from cli_helpers import forbid_subprocesses                                     # noqa: E402
from main import DEFAULT_ARTIFACTS_DIR                                          # noqa: E402
from mixed_app_fixtures import APP_NAME, MIXED_APP_SURFACES                     # noqa: E402
from outputs import FINDINGS_NAME, SURFACES_NAME                                # noqa: E402
import run_record                                                               # noqa: E402

from .api_stubs import audit_and_poll, client_over, post_an_audit               # noqa: E402
from .audit_stub import wait_for_the_worker                                     # noqa: E402
from .real_audit_fixtures import URL, stub_every_outside_stage                  # noqa: E402

# The four checks that report on this app. It carries no dependency manifest, so
# no bill of materials is built and the supply-chain check has no mapping to
# examine -- which is why this is four and `MIXED_APP_FINDINGS` is five.
EXPECTED_RULE_IDS = sorted(
    [PERMISSION_CHECK, TAINT_CHECK, QUERY_CHECK, AUDITABILITY_CHECK])

# What the result envelope carries beside the two documents. Eight now: the
# seven the endpoint has always answered with, plus `comparison`, which is the
# hosted arm of a `--compare-models` run and is null on every other path. Null
# means one arm ran -- never that a second arm found nothing.
EXPECTED_RESULT_KEYS = {"schema_version", "app", "artifacts_dir", "seconds",
                        "advisories_read", "findings", "surfaces", "comparison"}

# The version the reply carries today, pinned as a literal beside the constant
# it must equal. Imported alone it would agree with itself. 3 since a run gained
# a required `auditor`: an old page posts a body without one and is answered 400.
REPLY_SCHEMA_VERSION = 3

# Every boundary this run announces, in order. Seven of the eight: `publish` is
# the pipeline's, and `record_publish` replaces that stage with a recorder that
# announces nothing. Pinned as a list, because a page shows the audit advancing
# and a stage that stopped being announced would show as never reached.
EXPECTED_STAGES = ["fetch", "surfaces", "dependencies", "advisories",
                   "checks", "advice", "write"]

# The two answers this file reads. 422 is pydantic's, not the wrapper's: a body
# that fails the request model never reaches the handler, so it is not one of
# `run_routes.py`'s own codes to import.
ACCEPTED = 202
UNPROCESSABLE = 422


def audit_through_the_endpoint(monkeypatch, tmp_path: Path) -> dict:
    """Post one audit of a freshly written app and poll it to a terminal status."""
    stub_every_outside_stage(monkeypatch, tmp_path)
    client, _ = client_over(tmp_path)
    record = audit_and_poll(client, URL)
    assert record["status"] == "finished", record["error"]
    return record


def written_document(tmp_path: Path, record: dict, name: str) -> dict:
    """Read one artifact off disk from where the reply says the audit wrote it."""
    directory = tmp_path / record["result"]["artifacts_dir"]
    return json.loads((directory / name).read_text(encoding="utf-8"))


# --- the record the page ends up with -----------------------------------------

def test_the_run_finishes_and_carries_a_result(monkeypatch, tmp_path) -> None:
    """`status == finished` iff `result`, over a real audit rather than a stub."""
    record = audit_through_the_endpoint(monkeypatch, tmp_path)
    assert record["result"] is not None
    assert record["error"] is None


def test_the_result_holds_exactly_the_documented_keys(monkeypatch, tmp_path) -> None:
    """Eight keys: its version, the run's four facts, the two artifacts, and the comparison."""
    record = audit_through_the_endpoint(monkeypatch, tmp_path)
    assert set(record["result"]) == EXPECTED_RESULT_KEYS


def test_a_single_arm_audit_carries_a_null_comparison(monkeypatch, tmp_path) -> None:
    """One arm ran. `null` says so, and never that a second arm found nothing."""
    record = audit_through_the_endpoint(monkeypatch, tmp_path)
    assert record["result"]["comparison"] is None


def test_the_record_and_its_result_name_the_audited_app(monkeypatch, tmp_path) -> None:
    """The app is the audited tree's directory name, and never guessed from the URL."""
    record = audit_through_the_endpoint(monkeypatch, tmp_path)
    assert record["app"] == record["result"]["app"] == APP_NAME


def test_the_reply_carries_its_own_schema_version(monkeypatch, tmp_path) -> None:
    """The reply is versioned because the page that reads it ships separately.

    `frontend/dist/` is built by hand and committed, so a stale bundle can meet
    a fresh server in an ordinary checkout -- the one place in this project
    where a reader and a writer of the same shape are updated apart. The two
    documents inside carry their own versions and are not this one.
    """
    record = audit_through_the_endpoint(monkeypatch, tmp_path)
    assert record["schema_version"] == run_record.REPLY_SCHEMA_VERSION
    assert record["schema_version"] == REPLY_SCHEMA_VERSION


def test_the_stages_the_run_announced_are_the_ones_the_page_shows(monkeypatch,
                                                                  tmp_path) -> None:
    """A real run's own boundaries, in order: the progress display is not decoration."""
    record = audit_through_the_endpoint(monkeypatch, tmp_path)
    assert record["stages"] == EXPECTED_STAGES


def test_the_record_counts_are_the_documents_own_counts(monkeypatch, tmp_path) -> None:
    """The history list and the dashboard read different fields of one run; they agree."""
    record = audit_through_the_endpoint(monkeypatch, tmp_path)
    assert record["finding_count"] == record["result"]["findings"]["finding_count"]
    assert record["surface_count"] == MIXED_APP_SURFACES


def test_the_run_reports_the_wall_clock_it_took(monkeypatch, tmp_path) -> None:
    """Two durations, and the record's is the whole job: acceptance to terminal status."""
    record = audit_through_the_endpoint(monkeypatch, tmp_path)
    assert record["seconds"] >= record["result"]["seconds"]


# --- where it wrote, and what it wrote there ----------------------------------

def test_artifacts_dir_names_where_the_audit_really_wrote(monkeypatch, tmp_path) -> None:
    """Not re-derived and not guessed: the directory named must hold both artifacts."""
    record = audit_through_the_endpoint(monkeypatch, tmp_path)
    written = tmp_path / record["result"]["artifacts_dir"]
    assert Path(record["result"]["artifacts_dir"]) == DEFAULT_ARTIFACTS_DIR / APP_NAME
    assert record["artifacts_dir"] == record["result"]["artifacts_dir"]
    assert (written / FINDINGS_NAME).is_file()
    assert (written / SURFACES_NAME).is_file()


def test_the_run_reports_its_artifacts_present_and_current(monkeypatch, tmp_path) -> None:
    """Computed per request, over the directory this run actually wrote."""
    record = audit_through_the_endpoint(monkeypatch, tmp_path)
    assert record["artifacts_present"] is True
    assert record["artifacts_current"] is True


def test_the_surfaces_document_is_what_the_audit_wrote(monkeypatch, tmp_path) -> None:
    """Compared against the file on disk, so the reply cannot be a reshaped copy."""
    record = audit_through_the_endpoint(monkeypatch, tmp_path)
    assert record["result"]["surfaces"] == written_document(tmp_path, record, SURFACES_NAME)


def test_the_findings_document_is_what_the_audit_wrote(monkeypatch, tmp_path) -> None:
    """The same for the second artifact, so neither is right by the other's accident."""
    record = audit_through_the_endpoint(monkeypatch, tmp_path)
    assert record["result"]["findings"] == written_document(tmp_path, record, FINDINGS_NAME)


def test_each_document_carries_its_own_schema_version(monkeypatch, tmp_path) -> None:
    """The field a browser-shaped rewrite drops first, asserted on both documents."""
    result = audit_through_the_endpoint(monkeypatch, tmp_path)["result"]
    assert result["surfaces"]["schema_version"] == SURFACES_SCHEMA_VERSION
    assert result["findings"]["schema_version"] == FINDINGS_SCHEMA_VERSION


def test_the_run_really_audited_the_written_app(monkeypatch, tmp_path) -> None:
    """Non-vacuity: an audit that found nothing would satisfy every comparison above."""
    result = audit_through_the_endpoint(monkeypatch, tmp_path)["result"]
    assert result["surfaces"]["surface_count"] == MIXED_APP_SURFACES
    assert sorted(f["rule_id"] for f in result["findings"]["findings"]) == EXPECTED_RULE_IDS


def test_the_run_read_no_advisory_data_and_says_so(monkeypatch, tmp_path) -> None:
    """Trivy is stubbed absent, so the page is told there were no advisories to read."""
    result = audit_through_the_endpoint(monkeypatch, tmp_path)["result"]
    assert result["advisories_read"] is False


# --- the failure path a browser reaches first ---------------------------------

def test_a_body_with_no_url_is_rejected_before_anything_runs(monkeypatch, tmp_path) -> None:
    """A malformed body is 422, not a traceback and not an accepted run."""
    monkeypatch.chdir(tmp_path)
    forbid_subprocesses(monkeypatch)
    client, registry = client_over(tmp_path)
    assert client.post("/api/audit", json={}).status_code == UNPROCESSABLE
    assert registry.store.count() == 0


def test_an_accepted_audit_answers_202_before_it_has_run(monkeypatch, tmp_path) -> None:
    """The protocol itself: the reply is the run that will do it, not the audit's result."""
    stub_every_outside_stage(monkeypatch, tmp_path)
    client, registry = client_over(tmp_path)
    accepted = post_an_audit(client, URL)
    assert accepted.status_code == ACCEPTED
    assert accepted.json()["status"] == "running"
    wait_for_the_worker(registry)
