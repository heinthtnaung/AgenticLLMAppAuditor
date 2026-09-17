"""One fetched tree, one run that audited it, and a client that can read a line of it.

Shared by the two files that drive `GET /api/runs/{run_id}/source`:
`test_source_window.py`, whose subject is which lines come back, and
`test_source_refusals.py`, whose subject is every path that must not. One
staging, because both need the same tree behind the same run and two copies
would drift into two ideas of what a fetched tree looks like.

**The download root is redirected before anything reads it.** `source_routes`
derives the directory from `fetch_repo.DOWNLOAD_ROOT`, which is the relative
`fetched/` in a working checkout and may hold real cloned repositories -- code
this project does not own and must never read in a test. Every client built here
points that constant at `tmp_path` first.

**The tree is staged the way a fetch leaves one**: source inside, the pin
*beside* it, and no `.git` at all, because `_fetch_into` deletes the history once
it has read the commit. That last absence is not incidental -- it is why
`check_tree_matches_pin` can only ever answer "cannot be checked" here, which is
the `unchecked` field the reply carries.

A synthetic tree is weaker than a real one and the numbers below say so plainly:
one short UTF-8 Python file of known length, nothing oversized, nothing
malformed, no symlink, no shape nobody foresaw. What it buys is that every line
number asserted is a literal.

Like `api_stubs.py` and `key_fixtures.py`, this imports fastapi outright rather
than skipping; every file that imports it calls `pytest.importorskip` first.
"""

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import fetch_repo
import history_store
import run_record
import source_routes

SOURCE_ENDPOINT = "/api/runs/{run_id}/source"

OK = 200
REFUSED = 400
NO_SOURCE = 404
NO_SUCH_RUN = 404

APP = "demo-app"
URL = f"https://example.invalid/owner/{APP}"
AUDITOR = "Quokka Reviewer"

# The audited file, and its lines numbered from one the way an editor counts
# them. Twenty of them, so a window of six either side sits wholly inside the
# file in the middle and is clipped at both ends -- all three cases the
# arithmetic has.
SOURCE_FILE = "agent.py"
LINE_COUNT = 20
SOURCE_LINES = [f"line_{number:02d} = {number}" for number in range(1, LINE_COUNT + 1)]
SOURCE_TEXT = "\n".join(SOURCE_LINES) + "\n"

# A second file, one directory down, so "inside the tree" is a real question
# rather than one every path answers by sitting in the root.
NESTED_DIR = "tools"
NESTED_FILE = f"{NESTED_DIR}/shell.py"
NESTED_TEXT = "import os\n\n\ndef shell(command):\n    return os.system(command)\n"

# What the fetch recorded about the tree. The commit is what the refusal quotes
# the first twelve characters of, so it is a full-length one.
COMMIT = "a1b2c3d4" * 5
COMMIT_DATE = "2026-01-01T00:00:00+00:00"

# A run id of the shape `uuid4().hex` produces, which is what `RUN_ID` matches.
RUN_ID = "0" * 31 + "1"
FINISHED_AT = "2026-01-01T00:00:10+00:00"

# The store's own rule: a finished run has an envelope and only a finished run
# does. The source route never reads it -- it needs the record's `app` and
# nothing else -- so an empty one is stored rather than a plausible-looking
# transcript that no assertion here would be about.
EMPTY_ENVELOPE: dict = {}


def stage_tree(tmp_path: Path, app: str = APP) -> Path:
    """Write the tree a fetch would have left under `tmp_path`, pin and all.

    No `.git`: the real fetch deletes it once the commit is pinned, so a tree
    that carried one would be a tree this tool never produces.
    """
    root = tmp_path / "fetched"
    tree = root / app
    (tree / NESTED_DIR).mkdir(parents=True)
    (tree / SOURCE_FILE).write_text(SOURCE_TEXT, encoding="utf-8")
    (tree / NESTED_FILE).write_text(NESTED_TEXT, encoding="utf-8")
    fetch_repo.write_manifest(root, fetch_repo.manifest(app, URL, COMMIT, COMMIT_DATE))
    return tree


def a_finished_run(app: str | None = APP) -> run_record.RunRecord:
    """One stored run, in the state a completed audit leaves it -- app name included."""
    return run_record.RunRecord(
        run_id=RUN_ID, repo_url=URL, auditor=AUDITOR, options={},
        started_at=COMMIT_DATE, status=run_record.FINISHED,
        finished_at=FINISHED_AT, app=app)


def client_over(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                record: run_record.RunRecord | None = None) -> TestClient:
    """A client whose one run is the given record and whose download root is under `tmp_path`.

    The redirection is `fetch_repo.DOWNLOAD_ROOT`, the name `source_routes`
    reads at call time. Without it the route resolves against the checkout's own
    `fetched/`, which may hold repositories this project does not own.
    """
    monkeypatch.setattr(fetch_repo, "DOWNLOAD_ROOT", tmp_path / "fetched")
    store = history_store.open_store(tmp_path / "runs", create=True)
    stored = record if record is not None else a_finished_run()
    store.save(stored, EMPTY_ENVELOPE if stored.status == run_record.FINISHED else None)
    app = FastAPI()
    source_routes.register(app, store)
    return TestClient(app)


def a_client_and_its_tree(monkeypatch: pytest.MonkeyPatch,
                          tmp_path: Path) -> tuple[TestClient, Path]:
    """The ordinary starting point: a staged tree, and a client over the run that audited it."""
    tree = stage_tree(tmp_path)
    return client_over(monkeypatch, tmp_path), tree


def ask_for_source(client: TestClient, file: str, line: int,
                   run_id: str = RUN_ID) -> httpx.Response:
    """Ask for one window, whatever the answer -- the refusals are half the subject."""
    return client.get(SOURCE_ENDPOINT.format(run_id=run_id),
                      params={"file": file, "line": line})


def source_window(client: TestClient, file: str, line: int) -> dict:
    """One window, insisting the route answered rather than refused."""
    response = ask_for_source(client, file, line)
    assert response.status_code == OK, response.text
    return response.json()


def refusal_from(response: httpx.Response, status: int) -> str:
    """The sentence a refused request answered with, insisting on the status too."""
    assert response.status_code == status, response.text
    return response.json()["detail"]
