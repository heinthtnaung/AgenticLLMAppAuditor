"""Stages one `--compare-models` run over a written app, with nothing real behind it.

Shared by `tests/compare/test_compare_arms.py`, which asserts where the two
arms' artifacts land and how each is scored, and
`tests/compare/test_compare_arms_result.py`, which asserts what the run hands
back. Both need the same staging, and a second copy of it is how the two would
start comparing different things.

The run is driven under `monkeypatch.chdir(tmp_path)`, so the two relative
artifact constants resolve inside the temporary tree and the real `artifacts/`
is never written to. `key_drafting.DRAFTED_KEYS_DIR` is absolute, under
`grading_keys/`, so chdir cannot move it: it is redirected too, and one test
says where the draft landed rather than leaving it to be inferred.

Both clients and the knowledge base are replaced by plain functions;
`pipeline.publish` is replaced too, because exporting HTML and PDF needs a
renderer this suite does not require and is `tests/cli/test_export_reports*.py`'s
subject. Nothing here reaches a model, a network or a repository this project
does not own: the app is written into `tmp_path` by `mixed_app_fixtures`.
"""

import json
from pathlib import Path

import cloud_client
import compare_run
import fetch_repo
from keys import key_drafting
import main
import model_client
import pipeline
from cli_helpers import stub_knowledge
from mixed_app_fixtures import APP_NAME, PYTHON_FILE, write_mixed_app

CLOUD_MODEL = "vendor/some-hosted-model"
COMMIT = "d" * 40
UPSTREAM_URL = "https://example.invalid/owner/mixed-app"
COMMIT_DATE = "2026-01-01T00:00:00Z"

# One key entry, answered by the tool call the mixed app really carries, so the
# drafted key is scorable rather than empty.
TOOL_LINE = 7
DRAFTED_ENTRY = {"id": "K-01", "file": PYTHON_FILE, "line": TOOL_LINE, "owasp_id": "LLM06",
                 "llm_surface": "TOOL_CALL", "surface_name": "ShellTool",
                 "component": None, "detection": "static",
                 "title": "A shell tool", "description": "why"}

# The sentence in the drafting prompt that tells the stub which question it is
# being asked. `key_drafting.PROMPT` opens with it.
DRAFTING_MARKER = "drafting a security grading key"

ADVICE = "Treat it as data and gate the tool.\n\n```python\nchecked = approve(value)\n```"


def local_ask(prompt: str, model: str | None = None) -> str:
    """The local client's reply: the drafted key when asked for one, advice otherwise."""
    if DRAFTING_MARKER in prompt:
        return json.dumps([DRAFTED_ENTRY])
    return ADVICE


def cloud_ask(_prompt: str, _model: str | None = None) -> str:
    """The hosted client's reply. It is never asked to draft: only the local arm drafts."""
    return ADVICE


def drafts_dir(tmp_path: Path) -> Path:
    """Where a drafted key goes in a test: a tmp_path stand-in for grading_keys/drafts/."""
    return tmp_path / "grading_keys" / "drafts"


def stage(monkeypatch, tmp_path: Path) -> Path:
    """Write the app, pin it, replace both clients, and run inside the temporary tree."""
    repo = write_mixed_app(tmp_path)
    monkeypatch.setattr(key_drafting, "DRAFTED_KEYS_DIR", drafts_dir(tmp_path))
    fetch_repo.write_manifest(
        tmp_path, fetch_repo.manifest(APP_NAME, UPSTREAM_URL, COMMIT, COMMIT_DATE))
    stub_knowledge(monkeypatch)
    monkeypatch.setattr(model_client, "ask", local_ask)
    monkeypatch.setattr(model_client, "model_digest", lambda model=None: "0" * 64)
    monkeypatch.setattr(cloud_client, "ask", cloud_ask)
    monkeypatch.setattr(pipeline, "publish", lambda *args, **kwargs: None)
    monkeypatch.chdir(tmp_path)
    return repo


def compare(monkeypatch, tmp_path: Path) -> dict:
    """Run `--compare-models` end to end over the written app, and return its result."""
    repo = stage(monkeypatch, tmp_path)
    return compare_run.run(str(repo), main.DEFAULT_ARTIFACTS_DIR, CLOUD_MODEL)


def arm(tmp_path: Path, system: str) -> Path:
    """Where one arm's per-app artifacts landed."""
    return tmp_path / "artifacts" / system / APP_NAME


def read(path: Path) -> dict:
    """Read one written artifact."""
    return json.loads(path.read_text(encoding="utf-8"))
