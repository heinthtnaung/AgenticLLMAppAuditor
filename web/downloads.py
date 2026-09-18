"""Serves the files a run left on disk, and only those.

**Every reply is an attachment, including the HTML.** `report.html` is rendered
from the audited repository's own strings, so serving it inline would run that
repository's content as script in this server's origin -- the same origin as an
API with no authentication that clones anything it is asked to. A download is
what the user asked for anyway; `Content-Disposition` makes it the only thing
on offer.

**The caller never names a path.** A run id and an `arm` from a closed set of
two choose the directory, and the filename must be one of the names
`artifacts/names.py` owns. The join is checked after resolving besides, the way
`page.py` checks the built page's directory -- an allowlist and a containment
check answer different questions and both are cheap.

**The hosted arm's directory comes from the stored envelope**, which is the one
place it exists: only a `--compare-models` run has a second arm, so it was
never a column. That path is trusted exactly as `record.artifacts_dir` already
was -- both are written by this server from an audit's own result, never from a
request -- and the allowlist and containment check bound what can be read out
of either.
"""

import io
import zipfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response

from artifacts.names import ALL_NAMES
from history_store import HistoryStore
from run_record import RunRecord

# Everything a run can leave behind, as a set. One spelling, in `src/`, shared
# with the code that writes each file.
DOWNLOADABLE = frozenset(ALL_NAMES)

BUNDLE_NAME = "artifacts.zip"

# A ceiling on the archive built in memory. A run's artifacts are a few hundred
# kilobytes; this is far above that and far below anything that would trouble
# the process, so crossing it means something is wrong rather than large.
MAX_BUNDLE_BYTES = 64 * 1024 * 1024

# Told rather than guessed. `mimetypes` varies by machine, and a wrong type on a
# download is a file the browser renames.
_TYPES = {
    ".json": "application/json",
    ".md": "text/markdown",
    ".html": "text/html",
    ".pdf": "application/pdf",
}
_FALLBACK_TYPE = "application/octet-stream"

NO_SUCH_RUN = 404
NOT_DOWNLOADABLE = 404
SUPERSEDED = 409
TOO_LARGE = 413
UNKNOWN_ARM = 400

# Which audit's files to serve. A closed set of two, and the request's own
# vocabulary rather than the artifacts' -- `agentic_auditor` and
# `cloud_auditor` are what the documents and the scorer call the two systems,
# and a query string is not the place to make a caller spell them.
LOCAL_ARM = "local"
CLOUD_ARM = "cloud"
ARMS = (LOCAL_ARM, CLOUD_ARM)


def register(app: FastAPI, store: HistoryStore) -> None:
    """Attach the download routes to an application."""

    @app.get("/api/artifacts/{run_id}")
    def listing(run_id: str, arm: str = LOCAL_ARM) -> dict:
        """Which of the files this run wrote are on disk, and how large.

        Listed rather than assumed: a stage that could not run leaves its
        artifact absent, so a page that offered all sixteen links would offer
        some that answer 404. Absent is a fact about the run, and the panel says
        it rather than discovering it on a click.
        """
        directory = _directory(store, run_id, arm)
        return {
            "run_id": run_id,
            "arm": arm,
            "files": [{"name": name, "bytes": (directory / name).stat().st_size}
                      for name in ALL_NAMES if (directory / name).is_file()],
            "bundle": BUNDLE_NAME,
        }

    @app.get("/api/artifacts/{run_id}/" + BUNDLE_NAME, response_model=None)
    def bundle(run_id: str, arm: str = LOCAL_ARM) -> Response:
        """Every file one arm of this run actually wrote, in one archive."""
        directory = _directory(store, run_id, arm)
        present = [name for name in ALL_NAMES if (directory / name).is_file()]
        total = sum((directory / name).stat().st_size for name in present)
        if total > MAX_BUNDLE_BYTES:
            raise HTTPException(
                status_code=TOO_LARGE,
                detail=f"these artifacts total {total} bytes, over the "
                       f"{MAX_BUNDLE_BYTES} byte cap for one archive")
        return Response(
            content=_archive(directory, present),
            media_type="application/zip",
            # The arm is in the filename because both arms audit one app and
            # `directory.name` is that app for either of them -- two archives
            # called the same thing is one of them overwriting the other in a
            # downloads folder.
            headers=_attachment(f"{directory.name}-{arm}-{BUNDLE_NAME}"))

    @app.get("/api/artifacts/{run_id}/{name}", response_model=None)
    def one_file(run_id: str, name: str, arm: str = LOCAL_ARM) -> FileResponse:
        """One named artifact of one arm, as a download."""
        directory = _directory(store, run_id, arm)
        if name not in DOWNLOADABLE:
            raise HTTPException(
                status_code=NOT_DOWNLOADABLE,
                detail=f"{name!r} is not one of the files a run writes")
        asked_for = directory / name
        # Belt and braces beside the allowlist: resolved, and required to sit
        # directly under the run's own directory.
        if not asked_for.is_file() or asked_for.resolve().parent != directory.resolve():
            raise HTTPException(
                status_code=NOT_DOWNLOADABLE,
                detail=f"this run wrote no {name}; a stage that could not run "
                       "leaves its artifact absent rather than empty")
        return FileResponse(
            asked_for, media_type=_TYPES.get(asked_for.suffix, _FALLBACK_TYPE),
            headers=_attachment(name))


def _named(record: RunRecord, envelope: dict | None, arm: str) -> str | None:
    """Where one arm of a run wrote, by name, or None when that arm wrote nothing.

    The hosted arm's directory is in the envelope and nowhere else: it is not a
    column, because only a `--compare-models` run has one. An ordinary run has
    no `comparison`, which is why asking for its hosted arm is an absence rather
    than an error.
    """
    if arm == LOCAL_ARM:
        return record.artifacts_dir
    comparison = (envelope or {}).get("comparison")
    if not isinstance(comparison, dict):
        return None
    named = comparison.get("artifacts_dir")
    return named if isinstance(named, str) else None


def _directory(store: HistoryStore, run_id: str, arm: str = LOCAL_ARM) -> Path:
    """Where one arm wrote, refusing files that are gone or overwritten."""
    if arm not in ARMS:
        raise HTTPException(
            status_code=UNKNOWN_ARM,
            detail=f"{arm!r} is not an arm of a run; expected one of {ARMS}")
    found = store.get(run_id)
    if found is None:
        raise HTTPException(status_code=NO_SUCH_RUN, detail="no run has that id")
    record, envelope = found
    named = _named(record, envelope, arm)
    if named is None:
        raise HTTPException(
            status_code=NOT_DOWNLOADABLE,
            detail=f"this run wrote no {arm} artifacts; its status says why, and "
                   "only a --compare-models run has a hosted arm at all")
    # Asked about the directory this arm used, not about the record's own
    # column: the hosted arm's path is shared by every compare run of the app,
    # so it is overwritten on exactly the same terms.
    if store.overwritten_since(record, named):
        raise HTTPException(
            status_code=SUPERSEDED,
            detail="a later run of the same app overwrote these artifacts. This "
                   "run wrote to a directory keyed on the app rather than on "
                   "itself, which is how runs recorded before 2026-09-18 were "
                   "stored, so what is on disk is no longer what it produced -- "
                   "audit it again rather than reading another run's files under "
                   "this run's timestamp.")
    directory = Path(named)
    if not directory.is_dir():
        raise HTTPException(
            status_code=NOT_DOWNLOADABLE,
            detail=f"{named} is gone from disk. The run itself is "
                   "still readable -- its findings are stored -- but the files are not.")
    return directory


def _archive(directory: Path, names: list[str]) -> bytes:
    """The named files as one deflated zip, built in memory."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            archive.write(directory / name, arcname=name)
    return buffer.getvalue()


def _attachment(filename: str) -> dict:
    """Headers that make a reply a saved file rather than a rendered page."""
    return {"Content-Disposition": f'attachment; filename="{filename}"'}
