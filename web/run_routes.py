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
# Also 409, and a second name rather than a reuse: a finished run is not
# "already running". `downloads.py` sets the same precedent with `SUPERSEDED`.
NOT_FAILED = 409
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

    @app.delete("/api/runs/{run_id}")
    def forget_run(run_id: str) -> dict:
        """Forget one **failed** run. Refuses every other status by name.

        `docs/SCHEMAS.md` carries the argument: the CHECK constraint the
        narrowing rests on, and why the other two statuses are refused.
        `tests/web/test_failed_run_has_no_artifacts_dir.py` measures its one
        prose premise -- that a failed row names no `artifacts_dir` -- which is
        why nothing here branches defensively on a case no producer reaches.

        The row only: `artifacts/<app>/` is keyed on the app name and shared
        with every other run of that app. `runs/uploads/<run_id>/` survives too
        and is unreachable afterwards, because both upload routes gate on
        `store.get` -- `tests/web/test_uploads_serving.py` holds that an id no
        row carries answers 404, and a forgotten run's id is exactly that.
        Recorded in `docs/TODO.md`.
        """
        found = registry.store.get(run_id) if RUN_ID.match(run_id) else None
        if found is None:
            raise HTTPException(status_code=NO_SUCH_RUN, detail="no run has that id")
        record, _envelope = found
        if record.status != run_record.FAILED:
            # 409 and not 400: the request is well formed, and it is the run's
            # *state* that refuses it -- the same distinction this server
            # already draws when an audit is in flight.
            raise HTTPException(
                status_code=NOT_FAILED,
                detail=f"this run is {record.status}, and only a failed run may be "
                       "forgotten. A finished run's envelope is the only copy of its "
                       "findings once `artifacts/` is cleaned, and a running one "
                       "still has a worker writing to it")
        # The store's own answer, not an assumption: a row that vanished between
        # the read above and here is a 404 rather than a cheerful success.
        if not registry.store.delete(run_id):
            raise HTTPException(status_code=NO_SUCH_RUN, detail="no run has that id")
        # `forgotten` echoes what the caller sent and carries no information --
        # the page discards the body. It is here because every reply under
        # `/api/` carries a `schema_version`, and a 204 would be the one that
        # does not.
        return {"schema_version": run_record.REPLY_SCHEMA_VERSION, "forgotten": run_id}


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
