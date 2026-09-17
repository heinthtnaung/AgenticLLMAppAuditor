"""Files a person attached to a run, and the one route that hands them back.

**Not artifacts, on every count this project uses**: not produced by `src/`, not
byte-identical, not read by any phase, and not part of a schema a later phase
consumes. And one count no other object here has -- they are attacker-chosen
bytes arriving at an endpoint with no authentication.

**They change no finding.** Nothing under `src/` reads this directory, no check
joins on an upload, and `findings.json` is untouched. They are evidence for a
person reading the page; the audit does not know they exist.

**The stored filename is the upload id, never the client's name.** That is the
security property and not a naming convention: attacker-chosen bytes never
choose a path component. The name a browser sent lives only inside the record,
where it is data. Both ids in the route are server-generated 32-hex and checked
against the same pattern the run routes apply, for the reason recorded there --
it keeps a request-supplied string out of a filesystem join.
"""

import hashlib
import uuid
from dataclasses import replace
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from history_store import STORE_DIR, HistoryStore
from run_record import RunRecord
from run_routes import RUN_ID

# Anchored to the repository beside the history, not to the working directory,
# and `runs/` is gitignored -- so an upload is structurally uncommittable, the
# same protection `grading_keys/drafts/` has.
#
# The default, not the destination: `register` takes the directory, so a caller
# that redirects the store redirects these with it. Left as a module constant it
# was a second thing to remember, and forgetting it writes attacker-chosen bytes
# into the checkout.
DEFAULT_UPLOAD_DIR = STORE_DIR / "uploads"

# One file, all files of one run, how many, and how long a display name may be.
# Bounds rather than an allowlist: evidence may be any bytes, so the protection
# is on the way out instead.
MAX_UPLOAD_BYTES = 16 * 1024 * 1024
MAX_UPLOAD_TOTAL_BYTES = 64 * 1024 * 1024
MAX_UPLOADS_PER_RUN = 20
MAX_UPLOAD_NAME_LENGTH = 200

# Told, never guessed, and never the client's declared type: that is
# attacker-chosen and could only ever be echoed back, which is how a sniffed
# upload renders in this origin.
UPLOAD_TYPE = "application/octet-stream"

NO_SUCH_RUN = 404
NO_SUCH_UPLOAD = 404
REFUSED = 400
TOO_LARGE = 413

# Read in pieces so a body over the cap is refused without being buffered whole.
# `Content-Length` is the client's claim; the running total is the fact.
_CHUNK = 64 * 1024


def register(app: FastAPI, store: HistoryStore,
             upload_dir: Path | None = None) -> None:
    """Attach the upload routes to an application, writing under `upload_dir`."""
    held_in = DEFAULT_UPLOAD_DIR if upload_dir is None else upload_dir

    @app.post("/api/runs/{run_id}/uploads", status_code=201)
    async def attach(run_id: str, name: str, request: Request) -> dict:
        """Attach one file to a run as evidence. Changes no finding."""
        record = _run(store, run_id)
        _check_room(record, name)
        upload_id = uuid.uuid4().hex
        written = held_in / run_id / upload_id
        written.parent.mkdir(parents=True, exist_ok=True)
        # Bytes first, then the record. The opposite order is the one to avoid:
        # a stored attachment whose file was never written is a claim with no
        # evidence behind it, where a file no record mentions is only an orphan
        # on disk. The same reasoning the key routes now validate before writing.
        held = await _receive(request, written, _room_left(record))
        attached = {"upload_id": upload_id, "name": name[:MAX_UPLOAD_NAME_LENGTH],
                    "bytes": held["bytes"], "sha256": held["sha256"]}
        store.save(_with_upload(record, attached), _envelope_of(store, run_id))
        return attached

    @app.get("/api/runs/{run_id}/uploads/{upload_id}", response_model=None)
    def one_upload(run_id: str, upload_id: str) -> FileResponse:
        """One attached file, as a download and never as a rendered page."""
        record = _run(store, run_id)
        listed = next((u for u in record.uploads if u["upload_id"] == upload_id), None)
        if listed is None or not RUN_ID.match(upload_id):
            raise HTTPException(status_code=NO_SUCH_UPLOAD,
                                detail="this run has no such attachment")
        held = held_in / run_id / upload_id
        if not held.is_file():
            raise HTTPException(
                status_code=NO_SUCH_UPLOAD,
                detail="the run still lists this attachment; the file is gone from disk")
        return FileResponse(held, media_type=UPLOAD_TYPE, headers={
            "Content-Disposition": f'attachment; filename="{_safe(listed["name"])}"',
            # The type is told; this stops a browser overriding it by sniffing.
            "X-Content-Type-Options": "nosniff"})


def _run(store: HistoryStore, run_id: str) -> RunRecord:
    """The run these bytes belong to, refusing an id no row carries."""
    found = store.get(run_id) if RUN_ID.match(run_id) else None
    if found is None:
        raise HTTPException(status_code=NO_SUCH_RUN, detail="no run has that id")
    return found[0]


def _check_room(record: RunRecord, name: str) -> None:
    """Refuse before a byte is read, when the run is already at a cap."""
    if not name.strip():
        raise HTTPException(status_code=REFUSED, detail="an attachment needs a name")
    if len(record.uploads) >= MAX_UPLOADS_PER_RUN:
        raise HTTPException(
            status_code=REFUSED,
            detail=f"this run already has {MAX_UPLOADS_PER_RUN} attachments")
    if _room_left(record) <= 0:
        raise HTTPException(
            status_code=TOO_LARGE,
            detail=f"this run's attachments already total {MAX_UPLOAD_TOTAL_BYTES} bytes")


def _room_left(record: RunRecord) -> int:
    """How many more bytes this run may hold, across one file and all of them."""
    used = sum(upload["bytes"] for upload in record.uploads)
    return min(MAX_UPLOAD_BYTES, MAX_UPLOAD_TOTAL_BYTES - used)


async def _receive(request: Request, written: Path, limit: int) -> dict:
    """Stream the body to disk, refusing past the cap, and digest what landed.

    Streamed rather than read whole: a cap enforced after buffering is not a
    cap. The partial file is removed on refusal, so a rejected upload leaves
    nothing behind.
    """
    digest = hashlib.sha256()
    total = 0
    with written.open("wb") as sink:
        async for chunk in request.stream():
            total += len(chunk)
            if total > limit:
                sink.close()
                written.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=TOO_LARGE,
                    detail=f"an attachment may add at most {limit} more bytes to this run")
            digest.update(chunk)
            sink.write(chunk)
    return {"bytes": total, "sha256": digest.hexdigest()}


def _with_upload(record: RunRecord, attached: dict) -> RunRecord:
    """The same run, one attachment longer. The record is frozen."""
    return replace(record, uploads=[*record.uploads, attached])


def _envelope_of(store: HistoryStore, run_id: str) -> dict | None:
    """The run's stored envelope, so saving an attachment does not drop it."""
    found = store.get(run_id)
    return None if found is None else found[1]


def _safe(name: str) -> str:
    """A display name fit for a header: no quotes, controls or path separators.

    The only place a client-supplied string reaches a response header. Quotes
    and control characters would break out of the header; separators would not,
    since a recipient discards path information anyway -- but a filename that
    still reads like a path in the one header that carries one is worth not
    sending.
    """
    kept = (ch for ch in name
            if ch.isprintable() and ch not in '"\\/')
    return "".join(kept)[:MAX_UPLOAD_NAME_LENGTH] or "attachment"
