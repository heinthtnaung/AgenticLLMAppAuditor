"""The two fields a reply establishes rather than stores: are the files there, and are they this run's?

`artifacts_present` and `artifacts_current` are computed per request, and that is
the design rather than an optimisation: a stored flag about the filesystem
becomes a lie the moment someone cleans `artifacts/`, and a stale claim that a
run's evidence is present is exactly the shape of failure this tool exists to
expose. So both are asserted over a tree this file writes into `tmp_path` and,
in one case, deliberately does not write.

Two facts a page shows and this pins:

- **Cleaned artifacts leave the run readable.** `artifacts_present` goes false
  and the record still answers, because a finished run's findings live in the
  store. A row is never deleted for having lost its files.
- **A later run of the same app makes an older run's files not its own.**
  Artifacts are keyed on the app name, not on the run, so two audits of one URL
  share `artifacts/<system>/<app>/`. `artifacts_current` is how the older run
  says so; `test_downloads.py` is where that becomes a refusal.

Runs are written straight to the store here rather than audited, because the
subject is the directory a record names and not how it came to name it. The
whole file skips without the server packages: these are fields of a reply.
"""

import json

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from dataclasses import replace                    # noqa: E402
from pathlib import Path                           # noqa: E402

from outputs import FINDINGS_NAME                  # noqa: E402
from run_record import FAILED, FINISHED, RunRecord  # noqa: E402

from .api_stubs import client_over, read_run       # noqa: E402
from .audit_stub import URL, artifacts_dir_for     # noqa: E402

FINDING_COUNT = 4

# Two run ids and two times, so a superseded run has something to be superseded
# by and the comparison is on order rather than on identity.
EARLIER_ID = "a" * 32
LATER_ID = "b" * 32
EARLY = "2026-09-09T10:00:00+00:00"
LATE = "2026-09-09T12:00:00+00:00"

ENVELOPE = {"schema_version": 2, "app": "demo-app"}
TOOL_MESSAGE = "the repository could not be reached"


def plant_findings(tmp_path: Path) -> Path:
    """Write one artifact into the run's directory, so something is downloadable."""
    written = artifacts_dir_for(tmp_path)
    written.mkdir(parents=True)
    (written / FINDINGS_NAME).write_text(
        json.dumps({"schema_version": 7, "finding_count": FINDING_COUNT, "findings": []}),
        encoding="utf-8")
    return written


def a_finished_row(run_id: str, artifacts_dir: str | None,
                   started_at: str = LATE) -> RunRecord:
    """One finished run, stored directly so its directory and its time can be chosen."""
    accepted = RunRecord(run_id=run_id, repo_url=URL, options={"url": URL},
                         started_at=started_at)
    return replace(accepted, status=FINISHED, finished_at=LATE, seconds=1.0,
                   app="demo-app", artifacts_dir=artifacts_dir,
                   finding_count=FINDING_COUNT, surface_count=6)


def test_a_run_with_no_directory_reports_its_artifacts_absent(tmp_path) -> None:
    """`artifacts_dir` null implies `artifacts_present` false, with nothing to look at."""
    client, registry = client_over(tmp_path)
    registry.store.save(replace(a_finished_row(EARLIER_ID, None), status=FAILED,
                                error=TOOL_MESSAGE, finding_count=None,
                                surface_count=None), None)
    body = read_run(client, EARLIER_ID)
    assert body["artifacts_dir"] is None
    assert body["artifacts_present"] is False


def test_a_run_whose_directory_holds_a_file_reports_them_present(tmp_path) -> None:
    """Computed per request: a stored flag would be a lie the moment `artifacts/` is cleaned."""
    written = plant_findings(tmp_path)
    client, registry = client_over(tmp_path)
    registry.store.save(a_finished_row(EARLIER_ID, str(written)), ENVELOPE)
    assert read_run(client, EARLIER_ID)["artifacts_present"] is True


def test_a_run_whose_directory_was_cleaned_reports_them_absent(tmp_path) -> None:
    """The same run after `rm -rf artifacts/`: still readable, and honest about the files."""
    client, registry = client_over(tmp_path)
    registry.store.save(a_finished_row(EARLIER_ID, str(artifacts_dir_for(tmp_path))),
                        ENVELOPE)
    body = read_run(client, EARLIER_ID)
    assert body["artifacts_dir"] is not None
    assert body["artifacts_present"] is False


def test_a_run_nothing_wrote_over_reports_its_artifacts_current(tmp_path) -> None:
    """One audit of one app: the files on disk are the ones this run produced."""
    written = plant_findings(tmp_path)
    client, registry = client_over(tmp_path)
    registry.store.save(a_finished_row(EARLIER_ID, str(written)), ENVELOPE)
    assert read_run(client, EARLIER_ID)["artifacts_current"] is True


def test_a_run_a_later_one_overwrote_reports_its_artifacts_stale(tmp_path) -> None:
    """Artifacts are keyed on the app, so a second audit of one URL writes over the first."""
    written = plant_findings(tmp_path)
    client, registry = client_over(tmp_path)
    registry.store.save(a_finished_row(EARLIER_ID, str(written), EARLY), ENVELOPE)
    registry.store.save(a_finished_row(LATER_ID, str(written)), ENVELOPE)
    assert read_run(client, EARLIER_ID)["artifacts_current"] is False
    assert read_run(client, LATER_ID)["artifacts_current"] is True
