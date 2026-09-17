"""One run with somewhere of its own to keep attachments, and the post that adds one.

Four files drive `web/uploads.py` -- what attaching does, what the caps refuse,
what serving one back does, and where the bytes are written -- and all of them
need the same two things: a stored run to attach to, and an attachments
directory under `tmp_path`.

**Both are arguments now, and that is the whole point.** `register(app, store,
upload_dir)` resolves the directory once and closes it over both routes, so
redirecting a test's uploads is the same move as redirecting its store. It used
to be a module constant that every test here rebound, which made "somewhere
under `tmp_path`" a second thing to remember -- and forgetting it wrote
attacker-shaped bytes into the checkout. `test_uploads_destination.py` asserts
that the argument really is the only seam, which a rebound constant could not
have been asked to prove.

Imports fastapi and httpx outright; every module that imports this skips on the
web extra first.
"""

from dataclasses import replace
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

import run_routes
import uploads
from run_jobs import Registry
from run_record import FINISHED, RunRecord

from .audit_stub import AUDITOR, URL, open_a_store

# The run every fixture below stores, and an id that is well formed but unknown.
RUN_ID = "a" * 32
NO_SUCH_RUN_ID = "b" * 32

WHEN = "2026-09-09T12:00:00+00:00"
ENVELOPE = {"schema_version": 3, "app": "demo-app"}

# What a client calls the file it attaches, and what it holds. The bytes are not
# text-shaped, because the reply's type is told rather than sniffed.
DISPLAY_NAME = "third-party-sbom.json"
CONTENT = b"\x00\x01evidence from another tool\x02\x03"


def attachments_dir(tmp_path: Path) -> Path:
    """Where a test says its attachments go: inside the directory it owns."""
    return tmp_path / "attachments"


def application_with_uploads(tmp_path: Path,
                             upload_dir: Path | None = None) -> tuple[TestClient, Registry]:
    """A client over an application holding the run routes and the upload routes.

    Assembled the way `api.py` assembles them, over a store under `tmp_path`.
    The run routes are here because an attachment is looked up through the run.
    `upload_dir` is passed straight through, so a caller that wants the module's
    own default can ask for it by leaving it out -- which is what makes the
    default assertable.
    """
    app = FastAPI()
    registry = Registry(open_a_store(tmp_path))
    run_routes.register(app, registry)
    uploads.register(app, registry.store, upload_dir)
    return TestClient(app), registry


def a_finished_run(run_id: str = RUN_ID) -> RunRecord:
    """One run that got all the way through, which is what a person attaches evidence to."""
    accepted = RunRecord(run_id=run_id, repo_url=URL, auditor=AUDITOR,
                         options={"url": URL}, started_at=WHEN)
    return replace(accepted, status=FINISHED, finished_at=WHEN, seconds=1.0,
                   app="demo-app", finding_count=0, surface_count=0)


def a_run_to_attach_to(tmp_path: Path,
                       upload_dir: Path | None = None) -> tuple[TestClient, Registry, Path]:
    """A client, one stored finished run, and the directory its attachments land in."""
    written_to = attachments_dir(tmp_path) if upload_dir is None else upload_dir
    client, registry = application_with_uploads(tmp_path, written_to)
    registry.store.save(a_finished_run(), ENVELOPE)
    return client, registry, written_to


def attach(client: TestClient, content: bytes = CONTENT, name: str = DISPLAY_NAME,
           run_id: str = RUN_ID, **kwargs) -> httpx.Response:
    """Post one file to a run, with the display name as a query parameter."""
    return client.post(f"/api/runs/{run_id}/uploads", params={"name": name},
                       content=content, **kwargs)


def files_under(root: Path) -> list[Path]:
    """Every file that really landed anywhere beneath a directory."""
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def stored_uploads(registry: Registry, run_id: str = RUN_ID) -> list[dict]:
    """The attachment list the run record carries, read back from the store."""
    return registry.store.get(run_id)[0].uploads
