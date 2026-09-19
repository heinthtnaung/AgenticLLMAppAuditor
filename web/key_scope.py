"""Turns a run id into the folder that run drafted its grading key into.

**The one place that join happens**, which is what bounds every key route: the
only folder this module can answer with is `run_files.run_keys(...)`, so no
request can name a path outside `artifacts/runs/`. `grading_keys/` holds the
answers this tool is scored against, and it is unreachable from this server
rather than one directory away -- see `key_draft_store` for why it used to be
the other way round, and what that broke.

**The app name comes from the record, never from the caller.** A run audits one
app and the row already names it, so putting it in the URL would add a way for
the two to disagree -- a request naming a run and some other app's key. The run
id is the whole address.

Free of any route's own vocabulary, so both `key_routes` and `key_verify_route`
ask the same question and get the same refusals.
"""

from pathlib import Path

from fastapi import HTTPException

import run_files
from history_store import HistoryStore
from run_routes import RUN_ID

NO_SUCH_RUN = 404
NO_APP = 404


def for_run(store: HistoryStore, run_id: str) -> tuple[Path, str]:
    """This run's key folder and the app it drafted for, refusing a run with neither."""
    found = store.get(run_id) if RUN_ID.match(run_id) else None
    if found is None:
        raise HTTPException(status_code=NO_SUCH_RUN, detail="no run has that id")
    record = found[0]
    # A failed run has no app: it never got far enough to name one, so there is
    # no key it could have drafted and nothing to point a folder at. Refused as
    # an absence rather than answered with an empty folder, which would read as
    # "this run drafted no key" about a run that never could have.
    if not record.app:
        raise HTTPException(
            status_code=NO_APP,
            detail=f"this run is {record.status} and named no app, so it drafted "
                   "no grading key")
    return run_files.run_keys(run_id), record.app
