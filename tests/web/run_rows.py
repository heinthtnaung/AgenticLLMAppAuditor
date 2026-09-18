"""One run record in each of the three statuses, for the tests that forget one.

`DELETE /api/runs/{id}` is decided entirely by a run's status, so every test of
it needs a `failed` row to remove and a `finished` and a `running` row to be
refused. Spelled once here rather than in each of the three files below it --
`test_history_store_delete.py`, `test_run_delete.py` and
`test_failed_run_has_no_artifacts_dir.py` -- because a `finished` row built
slightly differently in two of them is a difference nobody would notice until
one of them stopped testing what it says.

**A failed row carries no `artifacts_dir` and no envelope**, and that is not a
convenience of these builders: it is the property the delete route's safety
argument rests on. `test_failed_run_has_no_artifacts_dir.py` proves the real
producers behave that way, so nothing here has to be believed.

Free of fastapi, like `audit_stub.py` beside it: the store and the record are
testable on a checkout where the server packages were never installed, and only
the file that drives an HTTP endpoint should have to skip.
"""

from dataclasses import replace
from pathlib import Path

from history_store import HistoryStore, open_store
from run_record import FAILED, FINISHED, RunRecord

URL = "https://example.invalid/owner/demo-app"

# Required on every record since the wire version went to 3.
AUDITOR = "Quokka Reviewer"

OPTIONS = {"url": URL, "semantic_probe": False}
APP = "demo-app"
ARTIFACTS = "artifacts/agentic_auditor/demo-app"

# One timestamp, at the precision `run_record.now()` writes: seconds.
WHEN = "2026-09-09T12:00:00+00:00"

# What a finished run stored, so a test can say out loud that forgetting a
# failed row destroys nothing of this kind.
ENVELOPE = {"schema_version": 3, "app": APP}

# The sentence a refused tool leaves on a failed run.
TOOL_MESSAGE = "the repository could not be reached"


def a_store(tmp_path: Path) -> HistoryStore:
    """An empty run history in a directory this test owns."""
    return open_store(tmp_path / "runs", create=True)


def running(run_id: str, started_at: str = WHEN) -> RunRecord:
    """One accepted run: nothing established yet, and a worker still on it."""
    return RunRecord(run_id=run_id, repo_url=URL, auditor=AUDITOR,
                     options=dict(OPTIONS), started_at=started_at)


def finished(run_id: str, started_at: str = WHEN,
             artifacts_dir: str = ARTIFACTS) -> RunRecord:
    """One run that got all the way through, naming the directory it wrote to."""
    return replace(running(run_id, started_at), status=FINISHED, finished_at=WHEN,
                   seconds=2.0, stages=["fetch", "write"], app=APP,
                   artifacts_dir=artifacts_dir, finding_count=4, surface_count=7)


def failed(run_id: str, started_at: str = WHEN) -> RunRecord:
    """One run that refused: an error, no envelope, and no directory named."""
    return replace(running(run_id, started_at), status=FAILED, finished_at=WHEN,
                   seconds=0.5, stages=["fetch"], error=TOOL_MESSAGE)
