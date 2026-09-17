"""One drafted grading key on disk, written by the code that really drafts them.

Shared by every file that drives the drafted-key editor -- sixteen of them now,
across `key_routes`, `key_verify_route` and `key_draft_store`, plus two helper
modules that build on this one. It began as three, and the list of names that
used to be here went stale the moment the routes split; what is worth saying is
not which files import it but what it guarantees to all of them: one drafted key
on disk, built by the code that really drafts them, under `tmp_path`.

**Nothing here writes to `grading_keys/drafts/`.** That folder holds real drafts
in a working checkout, and a test that wrote into it would edit the project's
own measurements.

**The redirection is one name, and it has to be `key_draft_store`'s.**
`keys/key_drafting.py` declares `DRAFTED_KEYS_DIR` and the store binds its own
reference with `from ... import`, so rebinding the source module's copy
redirects drafting and leaves these routes reading the checkout. It was briefly
two names -- `test_key_draft_store.py` tells that story and asserts that exactly
one module under `web/` may bind it, which is the fact this helper depends on.

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
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import key_draft_store
import key_routes
import key_verify_route
from artifacts.surface import PROMPT_TEMPLATE, TOOL_CALL, Surface
from keys import key_drafting, key_store
from keys.grading_keys import GROUND_TRUTH_SUFFIX, MANIFEST_SUFFIX, key_path
from parsing.languages import PYTHON

KEYS_ENDPOINT = "/api/keys"

OK = 200
REFUSED = 400
NO_SUCH_DRAFT = 404

APP = "demo-app"

# A second draft, so "the list" is never a list of one that happens to be right.
OTHER_APP = "second-app"

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


def plant(root: Path, app: str = APP, *, pin_fields: dict | None = None) -> Path:
    """Write one drafted key and its manifest under `root/drafts`, and return that folder.

    `pin_fields` adds to the manifest a real draft ships. With none, the pin is
    exactly what `key_store` writes -- naming no framework and no language,
    which is the state every drafted key is actually in.
    """
    drafts = root / "drafts"
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


# Every module binding its own reference to the drafts folder. A tuple of one,
# because it was a tuple of two for a day.
REDIRECTED_MODULES = (key_draft_store,)

# Both halves of the editor, registered as `web/api.py` registers them: side by
# side, so a reader auditing what this server exposes sees the route that writes
# `verified`. An application built from the first alone answers 405 to every
# claim, and every refusal about verifying would pass having proved nothing.
ROUTE_MODULES = (key_routes, key_verify_route)


def client_over(monkeypatch: pytest.MonkeyPatch, drafts: Path) -> TestClient:
    """An application whose drafted keys are the ones under `drafts`, and never the checkout's.

    `key_draft_store.DRAFTED_KEYS_DIR` is the name every read, write, listing
    and validation joins. Rebinding `keys.key_drafting.DRAFTED_KEYS_DIR`
    instead redirects drafting and leaves the store pointed at
    `grading_keys/drafts/` in the checkout, which holds real drafts.
    """
    for module in REDIRECTED_MODULES:
        monkeypatch.setattr(module, "DRAFTED_KEYS_DIR", drafts)
    app = FastAPI()
    for module in ROUTE_MODULES:
        module.register(app)
    return TestClient(app)


def planted_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                   pin_fields: dict | None = None) -> tuple[TestClient, Path]:
    """One drafted key on disk and a client that can reach it, which is how most tests start."""
    drafts = plant(tmp_path, pin_fields=pin_fields)
    return client_over(monkeypatch, drafts), drafts


def read_draft(client: TestClient, app: str = APP) -> dict:
    """One drafted key as the editor reads it, insisting the route answered."""
    response = client.get(f"{KEYS_ENDPOINT}/{app}")
    assert response.status_code == OK, response.text
    return response.json()


def save_draft(client: TestClient, key: dict, app: str = APP) -> httpx.Response:
    """Put one corrected key back, whatever the answer -- the refusals are the subject."""
    return client.put(f"{KEYS_ENDPOINT}/{app}", json={"key": key})


def saved(client: TestClient, key: dict, app: str = APP) -> dict:
    """Put one corrected key back and insist it was accepted, returning the reply."""
    response = save_draft(client, key, app)
    assert response.status_code == OK, response.text
    return response.json()
