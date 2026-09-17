"""Shared setup for the `--draft-key` tests: one app, pinned or not, and a model that answers.

Two files drive the drafting stage. `cli/test_pipeline_draft_key.py` is about
what the stage does inside a URL run; `cli/test_draft_key_flag.py` is about the
flag that gates it and the trees it applies to. Both stage the same thing --
the mixed-language app written into `tmp_path`, optionally pinned, with the
drafts folder redirected away from the repository's own `grading_keys/` -- so
it is spelled once here and the two cannot disagree about it.

Nothing here clones, launches a process or reaches a model: Syft, the fetch and
every model call are replaced at their seams.
"""

import json
from pathlib import Path

import pytest

import fetch_repo
import model_client
from cli_helpers import EMPTY_SCAN, STUB_ADVICE, stub_model, stub_syft
from fetch_helpers import COMMIT, COMMIT_DATE, URL
from keys import key_drafting
from keys.grading_keys import GROUND_TRUTH_SUFFIX, key_path
from mixed_app_fixtures import APP_NAME, PYTHON_FILE, write_mixed_app
from pipeline_helpers import point_download_root, record_fetch

# The opt-in that runs the drafting stage at all. Spelled as argv, because that
# is how a reader turns it on and the only way a test should reach it.
DRAFT_KEY = ("--draft-key",)

# The line `key_drafting.PROMPT` opens with, which tells the stubbed model which
# of the run's two questions it is being asked. Read from the prompt rather than
# copied: the tests that assert the drafting question was *never* asked would
# pass over a stale copy matching nothing, and nothing would say so.
DRAFTING_MARKER = key_drafting.PROMPT.splitlines()[0]

# One entry on the tool call the mixed app really carries, so the model names a
# defect the extractor found and the draft is not refused as ungrounded.
TOOL_LINE = 7


def an_entry(entry_id: object) -> dict:
    """One drafted entry on that tool call, labelled however the model labelled it."""
    return {"id": entry_id, "file": PYTHON_FILE, "line": TOOL_LINE, "owasp_id": "LLM06",
            "llm_surface": "TOOL_CALL", "surface_name": "ShellTool", "component": None,
            "detection": "static", "title": "A shell tool", "description": "why"}


DRAFTED_REPLY = json.dumps([an_entry("K-01")])

# The two ids a model can answer with that ended a successful run in a traceback:
# one surface named twice, one entry labelled `1` and one labelled `"K-02"`.
# `key_document` sorts on `(file, line, id)`, so the pair reached `sorted` and
# raised `TypeError` -- which is in neither `pipeline.DRAFTING_FAILURES` nor
# `main.EXPECTED_FAILURES`. **No hand edit anywhere: a model reply is enough**,
# which is what separates this from every other shape in this family.
NUMERIC_ID = 1
LABELLED_ID = "K-02"
MIXED_ID_REPLY = json.dumps([an_entry(NUMERIC_ID), an_entry(LABELLED_ID)])

# The same two entries, both labelled: the off position that says what the drop
# is about. Two entries on one surface is a promotion refusal, not a drafting
# one, so both of these must survive.
BOTH_LABELLED_REPLY = json.dumps([an_entry("K-01"), an_entry(LABELLED_ID)])


def drafts_dir(tmp_path: Path) -> Path:
    """Where a drafted key goes in a test: a tmp_path stand-in for grading_keys/drafts/."""
    return tmp_path / "grading_keys" / "drafts"


def drafted_key(tmp_path: Path) -> Path:
    """Where this run's drafted key should have landed."""
    return key_path(APP_NAME, GROUND_TRUTH_SUFFIX, drafts_dir(tmp_path))


def drafting_model(monkeypatch: pytest.MonkeyPatch,
                   reply: str = DRAFTED_REPLY) -> list[str]:
    """Answer the drafting question with `reply` and everything else with advice.

    The reply is a parameter because what a *model* can answer with is now a
    subject of its own: `MIXED_ID_REPLY` is a legal reply that used to end the
    run in a traceback.
    """
    seen: list[str] = []

    def answer(prompt: str, model: str | None = None) -> str:
        """Record the prompt, then reply as the model the run expects."""
        seen.append(prompt)
        return reply if DRAFTING_MARKER in prompt else STUB_ADVICE

    stub_model(monkeypatch)
    monkeypatch.setattr(model_client, "ask", answer)
    return seen


def drafting_prompts(seen: list[str]) -> list[str]:
    """The prompts out of a recorded run that asked the model to draft a key."""
    return [prompt for prompt in seen if DRAFTING_MARKER in prompt]


def _plant_app(monkeypatch: pytest.MonkeyPatch, root: Path, drafts: Path,
               pinned: bool) -> Path:
    """Write the app under `root`, pin it if asked, and redirect the drafts folder."""
    stub_syft(monkeypatch, EMPTY_SCAN)
    repo = write_mixed_app(root)
    if pinned:
        fetch_repo.write_manifest(
            root, fetch_repo.manifest(APP_NAME, URL, COMMIT, COMMIT_DATE))
    monkeypatch.setattr(key_drafting, "DRAFTED_KEYS_DIR", drafts)
    return repo


def fetched_tree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, pinned: bool) -> Path:
    """Plant the tree a fetch would return, and stub the fetch to hand it back."""
    root = point_download_root(monkeypatch, tmp_path)
    repo = _plant_app(monkeypatch, root, drafts_dir(tmp_path), pinned)
    record_fetch(monkeypatch, result=repo)
    return repo


def local_tree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, pinned: bool) -> Path:
    """Plant the same app as a directory the user points at: no fetch, no publish."""
    return _plant_app(monkeypatch, tmp_path, drafts_dir(tmp_path), pinned)
