"""Serves the files a run left on disk, and only those.

**Every reply is an attachment, including the HTML.** `report.html` is rendered
from the audited repository's own strings, so serving it inline would run that
repository's content as script in this server's origin -- the same origin as an
API with no authentication that clones anything it is asked to. A download is
what the user asked for anyway; `Content-Disposition` makes it the only thing
on offer.

**The caller never names a path.** A run id chooses the directory, and the
filename must be one of the names `artifacts/names.py` owns. The join is checked
after resolving besides, the way `page.py` checks the built page's directory --
an allowlist and a containment check answer different questions and both are
cheap.
"""

import io
import zipfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response

from artifacts.names import ALL_NAMES
from history_store import HistoryStore

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


def register(app: FastAPI, store: HistoryStore) -> None:
    """Attach the download routes to an application."""

    @app.get("/api/artifacts/{run_id}")
    def listing(run_id: str) -> dict:
        """Which of the files this run wrote are on disk, and how large.

        Listed rather than assumed: a stage that could not run leaves its
        artifact absent, so a page that offered all sixteen links would offer
        some that answer 404. Absent is a fact about the run, and the panel says
        it rather than discovering it on a click.
        """
        directory = _directory(store, run_id)
        return {
            "run_id": run_id,
            "files": [{"name": name, "bytes": (directory / name).stat().st_size}
                      for name in ALL_NAMES if (directory / name).is_file()],
            "bundle": BUNDLE_NAME,
        }

    @app.get("/api/artifacts/{run_id}/" + BUNDLE_NAME, response_model=None)
    def bundle(run_id: str) -> Response:
        """Every file this run actually wrote, in one archive."""
        directory = _directory(store, run_id)
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
            headers=_attachment(f"{directory.name}-{BUNDLE_NAME}"))

    @app.get("/api/artifacts/{run_id}/{name}", response_model=None)
    def one_file(run_id: str, name: str) -> FileResponse:
        """One named artifact, as a download."""
        directory = _directory(store, run_id)
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


def _directory(store: HistoryStore, run_id: str) -> Path:
    """Where this run wrote, refusing a run whose files are gone or overwritten."""
    found = store.get(run_id)
    if found is None:
        raise HTTPException(status_code=NO_SUCH_RUN, detail="no run has that id")
    record, _ = found
    if record.artifacts_dir is None:
        raise HTTPException(
            status_code=NOT_DOWNLOADABLE,
            detail="this run wrote no artifacts; its status says why")
    if store.superseded(record):
        raise HTTPException(
            status_code=SUPERSEDED,
            detail="a later run of the same app overwrote this run's artifacts. "
                   "Artifacts are keyed on the app name, not on the run, so what "
                   "is on disk is no longer what this run produced -- audit it "
                   "again rather than reading another run's files under this "
                   "run's timestamp.")
    directory = Path(record.artifacts_dir)
    if not directory.is_dir():
        raise HTTPException(
            status_code=NOT_DOWNLOADABLE,
            detail=f"{record.artifacts_dir} is gone from disk. The run itself is "
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
