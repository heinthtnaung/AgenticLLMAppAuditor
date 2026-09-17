"""A finished run whose artifacts directory holds exactly the files a test names.

Three files drive `web/downloads.py` -- one named file, the listing and the
archive, and the four ways a run has nothing to give -- and all three need the
same two things: a row in the store that names a directory, and a directory
holding some subset of `ALL_NAMES`. Spelled once here, so "which files exist" is
always the test's own decision and never a leftover from another test.

The content of each planted file is derived from its name, so an endpoint that
served the right *number* of bytes from the wrong file is still caught.

Imports fastapi through `api_stubs`; every module that imports this skips on the
web extra first.
"""

from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from artifacts.names import ALL_NAMES
from run_jobs import Registry
from run_record import FINISHED, RunRecord

from .api_stubs import client_over
from .audit_stub import AUDITOR, URL, artifacts_dir_for

# The run every fixture below stores, and a second one for the superseded case.
RUN_ID = "a" * 32
LATER_RUN_ID = "b" * 32

EARLY = "2026-09-09T10:00:00+00:00"
LATE = "2026-09-09T12:00:00+00:00"

ENVELOPE = {"schema_version": 2, "app": "demo-app"}

# Three names, one of each kind a browser treats differently: a document, a
# report, and the HTML rendered from the audited repository's own strings.
SOME_NAMES = ("findings.json", "report.md", "report.html")


def contents_of(name: str) -> str:
    """What a planted file holds: its own name, so a mixed-up file is visible."""
    return f"the contents of {name}\n"


def plant(directory: Path, names: tuple[str, ...]) -> Path:
    """Write exactly these artifact names into a directory, and nothing else."""
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        assert name in ALL_NAMES, f"{name} is not a file a run writes"
        (directory / name).write_text(contents_of(name), encoding="utf-8")
    return directory


def a_finished_row(run_id: str, artifacts_dir: str | None,
                   started_at: str = LATE) -> RunRecord:
    """One finished run, stored directly so its directory and its time are the test's."""
    accepted = RunRecord(run_id=run_id, repo_url=URL, auditor=AUDITOR,
                         options={"url": URL}, started_at=started_at)
    return replace(accepted, status=FINISHED, finished_at=LATE, seconds=1.0,
                   app="demo-app", artifacts_dir=artifacts_dir,
                   finding_count=0, surface_count=0)


def a_run_holding(tmp_path: Path,
                  names: tuple[str, ...]) -> tuple[TestClient, Registry, Path]:
    """A client, and one finished run whose directory holds exactly these files."""
    directory = plant(artifacts_dir_for(tmp_path), names)
    client, registry = client_over(tmp_path)
    registry.store.save(a_finished_row(RUN_ID, str(directory)), ENVELOPE)
    return client, registry, directory
