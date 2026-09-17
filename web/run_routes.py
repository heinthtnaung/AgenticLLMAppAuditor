"""The audit endpoint and the run history: accept a job, then answer about it.

`POST /api/audit` returns **202 and a run record**, not a finished audit. The
record it returns is the same shape a poll returns later in that run's life, so
the page needs one parser rather than one per endpoint.

A tool refusal is no longer an HTTP status. An unreachable URL, a name a grading
key owns, a tree over the size cap -- those are raised after the 202, so they
arrive as `status: failed` with the sentence the command line would have
printed. The 400 that remains is the request rules only, checked before any row
is written.
"""

import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from audit_request import AuditRequest
from downloads import DOWNLOADABLE
from history_store import HistoryStore
import run_record
from run_jobs import Busy, Registry
from reporting.progress import STAGES
from run_record import RunRecord

REFUSED = 400
NO_SUCH_RUN = 404
ALREADY_RUNNING = 409
ACCEPTED = 202

# `uuid4().hex`. Checked here so a malformed id never reaches the store at all,
# and because "no run has that id" is true of a malformed one too. The download
# routes do not apply it: they look the run up first, and a store that holds no
# such row is what refuses them.
RUN_ID = re.compile(r"^[0-9a-f]{32}$")


class AuditOptions(BaseModel):
    """The JSON body the page posts, mirroring the command line's options."""

    url: str
    auditor: str = ""
    model: str = ""
    semantic_probe: bool = False
    draft_key: bool = False
    compare_models: bool = False
    cloud_model: str = ""


def register(app: FastAPI, registry: Registry) -> None:
    """Attach the audit and history routes to an application."""

    @app.post("/api/audit", status_code=ACCEPTED)
    def audit(options: AuditOptions) -> dict:
        """Accept one audit and answer with the run that will do it."""
        named = options.model_dump()
        auditor = named.pop("auditor")
        asked = AuditRequest(**named)
        # Two rule sets, one refusal list: what may be audited, and who says so.
        refused = asked.refusals() + run_record.auditor_refusals(auditor)
        if refused:
            raise HTTPException(status_code=REFUSED, detail="; ".join(refused))
        try:
            return _body(registry.store, registry.start(asked, auditor))
        except Busy as busy:
            raise HTTPException(status_code=ALREADY_RUNNING, detail=str(busy)) from busy

    @app.get("/api/stages")
    def stages() -> dict:
        """Every boundary an audit can announce, in order.

        Served rather than restated in JavaScript. The page needs the whole list
        to show what has *not* happened yet, and a second copy of a closed
        vocabulary across a language boundary is how the two copies start
        disagreeing -- the defect this project already records about the JSX
        rebuilding a probe id.
        """
        return {"schema_version": run_record.REPLY_SCHEMA_VERSION,
                "stages": list(STAGES)}

    @app.get("/api/runs")
    def history() -> dict:
        """The newest runs, and how many the store holds in total."""
        store = registry.store
        return {
            "schema_version": run_record.REPLY_SCHEMA_VERSION,
            # Not `len(runs)`: the list is capped, and a reader comparing the two
            # is how you learn the history is longer than the page shows.
            "stored_run_count": store.count(),
            "runs": [run_record.summary(_body(store, record))
                     for record in store.recent()],
        }

    @app.get("/api/runs/{run_id}")
    def one_run(run_id: str) -> dict:
        """One run, with the audit's own envelope once it has finished."""
        found = registry.store.get(run_id) if RUN_ID.match(run_id) else None
        if found is None:
            raise HTTPException(status_code=NO_SUCH_RUN, detail="no run has that id")
        record, envelope = found
        return _body(registry.store, record, envelope)


def _body(store: HistoryStore, record: RunRecord, envelope: dict | None = None) -> dict:
    """One run as a reply, with what only a reader can establish added."""
    return run_record.body(
        record, result=envelope,
        artifacts_present=_present(record),
        # An older run whose directory a newer run has written over. Reported
        # rather than hidden: the findings this run recorded are still true, but
        # the files on disk are no longer the ones it wrote.
        artifacts_current=not store.superseded(record))


def _present(record: RunRecord) -> bool:
    """Whether this run's directory is on disk and holds anything downloadable.

    Coarse on purpose, and computed per request rather than stored: a flag about
    the filesystem becomes a lie the moment someone cleans `artifacts/`, and it
    is not a claim that every file is there -- the download route answers that
    one file at a time.
    """
    if record.artifacts_dir is None:
        return False
    directory = Path(record.artifacts_dir)
    return directory.is_dir() and any((directory / name).is_file()
                                      for name in DOWNLOADABLE)
