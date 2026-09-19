"""One drafted grading key on disk, written by the code that really drafts them.

Shared by every file that drives the drafted-key editor -- sixteen of them now,
across `key_routes`, `key_verify_route` and `key_draft_store`, plus two helper
modules that build on this one. It began as three, and the list of names that
used to be here went stale the moment the routes split; what is worth saying is
not which files import it but what it guarantees to all of them: one drafted key
on disk, built by the code that really drafts them, under `tmp_path`.

**Nothing here writes to `grading_keys/drafts/`.** That folder holds real drafts
in a working checkout, and a test that wrote into it would edit the project's
own measurements. Since the routes became run-scoped nothing *could*: the
server can only name a folder under `artifacts/runs/`, and the redirection below
moves that root rather than a drafts directory.

**The redirection is one name, and it is `run_files.RUN_ARTIFACTS_ROOT`.**
`key_scope.for_run` is the only place a run id becomes a folder and it can only
answer with `run_files.run_keys(...)`, so moving that root moves every key path
this server can reach. It used to be `key_draft_store.DRAFTED_KEYS_DIR`, back
when the routes read the checkout's drafts folder and could never see the key a
browser-started run had actually written.

**A key is addressed by run here, because that is how the routes address it.**
One `RUN_ID`, one row in a real history store, and the app name comes back off
that row -- so a test cannot ask for one app's key through another app's run,
which is a mismatch the old app-in-the-URL shape allowed.

**The key is built by `key_drafting`, not transcribed.** `key_document` decides
the thirteen top-level fields and `anchored` reads each `code_anchor` off the
source at the line it names, so a test asserting what an edit may not touch is
asserting it against the document a real `--draft-key` run produces. The
manifest comes from `key_store.manifest` for the same reason: a drafted pin
names no framework and no language, which is exactly why a draft always has one
promotion refusal outstanding and why the editor reports rather than enforces
them.

A synthetic tree is weaker than a real one, and this one is very small: two
short Python files, no unreadable source, no shape nobody foresaw. What it buys
is that every count below is a literal.

Like `api_stubs.py`, this imports fastapi outright rather than skipping: every
file that imports it calls `pytest.importorskip` first, so a clean checkout with
no web extra installed skips those files and still runs the rest.
"""

import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import key_routes
import key_verify_route
import run_files
from artifacts.surface import PROMPT_TEMPLATE, TOOL_CALL, Surface
from keys import key_drafting, key_store
from keys.grading_keys import GROUND_TRUTH_SUFFIX, MANIFEST_SUFFIX, key_path
from parsing.languages import PYTHON

from .api_stubs import open_a_store
from .run_rows import ENVELOPE, finished

# The one run every test here drafts under. Thirty-two hex characters, because
# `run_routes.RUN_ID` is what `key_scope` checks the id against before it
# reaches a filesystem join.
RUN_ID = "d" * 32

# Where that run's key is read and written. A run, not an app: the app name is
# read off the record server-side.
KEYS_ENDPOINT = f"/api/runs/{RUN_ID}/key"

OK = 200
REFUSED = 400
NO_SUCH_DRAFT = 404

APP = "demo-app"

# The audited tree the anchors are quoted from. Two files, so an entry's `file`
# is a real choice and a re-sort has something to order.
AGENT_FILE = "agent.py"
TOOLS_FILE = "tools.py"

AGENT_SOURCE = '''"""A very small support agent."""
from langchain.prompts import ChatPromptTemplate

PROMPT = ChatPromptTemplate.from_template("You are a support agent. {question}")
'''

TOOLS_SOURCE = '''import os


def shell(command):
    return os.system(command)
'''

# Where each entry is anchored, and the text `anchored()` will read there.
PROMPT_LINE = 4
SHELL_LINE = 5
PROMPT_ANCHOR = 'PROMPT = ChatPromptTemplate.from_template("You are a support'
SHELL_ANCHOR = "return os.system(command)"

# The three entries a drafted key holds here, in the order a model happened to
# name them -- which is not `(file, line, id)` order. `key_document` sorts them
# on the way in, so what lands on disk is K-01, K-03, K-02.
DRAFTED_ENTRIES = [
    {"id": "K-02", "file": TOOLS_FILE, "line": SHELL_LINE, "owasp_id": "LLM06",
     "llm_surface": "TOOL_CALL", "surface_name": "shell", "component": None,
     "detection": "static", "title": "a shell tool with no check in front of it",
     "description": "the agent can run any command the model writes"},
    {"id": "K-01", "file": AGENT_FILE, "line": PROMPT_LINE, "owasp_id": "LLM01",
     "llm_surface": "PROMPT_TEMPLATE", "surface_name": "ChatPromptTemplate.from_template",
     "component": None, "detection": "static",
     "title": "the question lands inside the instructions",
     "description": "the template interpolates user text into the system prompt"},
    {"id": "K-03", "file": AGENT_FILE, "line": PROMPT_LINE, "owasp_id": "LLM06",
     "llm_surface": "PROMPT_TEMPLATE", "surface_name": "ChatPromptTemplate.from_template",
     "component": None, "detection": "static",
     "title": "the same template reaches a tool",
     "description": "what the template produces is passed to the shell tool"},
]

# The two fields of a drafted key an edit is allowed to change: the entries a
# human corrects, and the count derived from them. Every other top-level field
# is identity, standing, or what the extractor found.
CORRECTABLE_FIELDS = {"findings", "finding_count"}

# How many entries the planted draft holds, and the order they are stored in.
ENTRY_COUNT = 3
STORED_ORDER = ["K-01", "K-03", "K-02"]

# The surfaces the extractor found, which is what `expected_surfaces` records --
# never what the model said, so a key can tell a missed surface from a bad find.
SURFACES = [
    Surface(PROMPT_TEMPLATE, "ChatPromptTemplate.from_template", AGENT_FILE,
            PROMPT_LINE, PYTHON, ""),
    Surface(TOOL_CALL, "shell", TOOLS_FILE, SHELL_LINE, PYTHON, ""),
]
SURFACE_COUNT = 2

COMMIT = "a1b2c3d4" * 5
UPSTREAM_URL = "https://example.invalid/owner/demo-app"
COMMIT_DATE = "2026-01-01T00:00:00+00:00"

# What `fetch_repo` recorded about the tree, which is all a drafted pin can say.
FETCHED_PIN = {"upstream_url": UPSTREAM_URL, "upstream_commit": COMMIT,
               "upstream_commit_date": COMMIT_DATE}

# The two fields a drafted manifest cannot carry and a human supplies at
# promotion. Adding them is what turns the one standing refusal into none.
HUMAN_PIN_FIELDS = {"framework": "langchain", "language": "python"}


def write_tree(root: Path) -> Path:
    """Write the two-file app the anchors are quoted from, and return its directory."""
    app_dir = root / "tree"
    app_dir.mkdir(parents=True)
    (app_dir / AGENT_FILE).write_text(AGENT_SOURCE, encoding="utf-8")
    (app_dir / TOOLS_FILE).write_text(TOOLS_SOURCE, encoding="utf-8")
    return app_dir


def a_drafted_key(root: Path, app: str = APP) -> dict:
    """The key a `--draft-key` run over that tree would have written."""
    anchored = key_drafting.anchored(DRAFTED_ENTRIES, write_tree(root))
    return key_drafting.key_document(app, anchored, COMMIT, SURFACES)


def keys_dir(root: Path, run_id: str = RUN_ID) -> Path:
    """Where a run drafts, under a movable root: the shape `run_files` builds.

    Spelled here so `client_over` can point the real `run_files.run_keys` at it
    and have the two agree. A test that built some other shape would be reading
    a folder no route could ever name.
    """
    return root / "artifacts" / "runs" / run_id / "keys"


def plant(root: Path, app: str = APP, *, pin_fields: dict | None = None) -> Path:
    """Write one drafted key and its manifest into the run's own folder, and return it.

    `pin_fields` adds to the manifest a real draft ships. With none, the pin is
    exactly what `key_store` writes -- naming no framework and no language,
    which is the state every drafted key is actually in.
    """
    drafts = keys_dir(root)
    drafts.mkdir(parents=True, exist_ok=True)
    key_store.write(app, a_drafted_key(root / app, app), FETCHED_PIN, drafts)
    if pin_fields:
        pin_path = key_path(app, MANIFEST_SUFFIX, drafts)
        pin = json.loads(pin_path.read_text(encoding="utf-8"))
        pin_path.write_text(json.dumps({**pin, **pin_fields}, indent=2, sort_keys=True),
                            encoding="utf-8")
    return drafts


def key_on_disk(drafts: Path, app: str = APP) -> dict:
    """The drafted key as it stands on disk, which is what a save has to have changed."""
    return json.loads(
        key_path(app, GROUND_TRUTH_SUFFIX, drafts).read_text(encoding="utf-8"))


def entry_ids(key: dict) -> list[str]:
    """The ids of a key's entries, in the order the document holds them."""
    return [entry["id"] for entry in key["findings"]]


def entry_named(key: dict, entry_id: str) -> dict:
    """One entry of a key, by the id it was drafted under."""
    found = [entry for entry in key["findings"] if entry["id"] == entry_id]
    assert len(found) == 1, f"expected exactly one {entry_id}, got {len(found)}"
    return found[0]


# Both halves of the editor, registered as `web/api.py` registers them: side by
# side, so a reader auditing what this server exposes sees the route that writes
# `verified`. An application built from the first alone answers 405 to every
# claim, and every refusal about verifying would pass having proved nothing.
ROUTE_MODULES = (key_routes, key_verify_route)


def client_over(monkeypatch: pytest.MonkeyPatch, drafts: Path,
                app_name: str = APP) -> TestClient:
    """An application whose one run drafted into `drafts`, and which can reach nothing else.

    The real `run_files.run_keys` runs -- only its root is moved -- so a test
    reads through the same join the server uses. The shape is asserted rather
    than assumed: a folder that is not `<root>/artifacts/runs/<run_id>/keys`
    would leave the routes reading somewhere this fixture never wrote, and every
    test over it would pass on a 404 it was not asking about.
    """
    assert drafts.name == "keys" and drafts.parent.name == RUN_ID, (
        f"{drafts} is not a run's key folder; build it with `keys_dir`")
    monkeypatch.setattr(run_files, "RUN_ARTIFACTS_ROOT", drafts.parents[1])
    history = open_a_store(drafts.parents[3])
    # With the envelope, because the store's own CHECK constraint ties the two:
    # `(status = 'finished') = (envelope IS NOT NULL)`. A key belongs to a run
    # that got far enough to draft one, so `finished` is the honest status here.
    history.save(replace(finished(RUN_ID), app=app_name), ENVELOPE)
    application = FastAPI()
    for module in ROUTE_MODULES:
        module.register(application, history)
    return TestClient(application)


def planted_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                   pin_fields: dict | None = None) -> tuple[TestClient, Path]:
    """One drafted key on disk and a client that can reach it, which is how most tests start."""
    drafts = plant(tmp_path, pin_fields=pin_fields)
    return client_over(monkeypatch, drafts), drafts


def read_draft(client: TestClient, endpoint: str = KEYS_ENDPOINT) -> dict:
    """One drafted key as the editor reads it, insisting the route answered."""
    response = client.get(endpoint)
    assert response.status_code == OK, response.text
    return response.json()


def save_draft(client: TestClient, key: dict,
               endpoint: str = KEYS_ENDPOINT) -> httpx.Response:
    """Put one corrected key back, whatever the answer -- the refusals are the subject."""
    return client.put(endpoint, json={"key": key})


def saved(client: TestClient, key: dict, endpoint: str = KEYS_ENDPOINT) -> dict:
    """Put one corrected key back and insist it was accepted, returning the reply."""
    response = save_draft(client, key, endpoint)
    assert response.status_code == OK, response.text
    return response.json()
