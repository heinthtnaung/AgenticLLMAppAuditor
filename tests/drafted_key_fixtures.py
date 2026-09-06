"""One drafted grading key, and the fetch pin that is written beside it.

Several files under `tests/compare/` need the same pair: one entry in the shape
the drafting prompt asks the model for, and the pin `key_store.write` is handed.
Both are spelled once here so those files cannot disagree about them.

The pin is built by `fetch_repo.manifest` -- the function that writes a real one
-- rather than by hand, so a change to a fetched pin's shape reaches these tests
instead of passing them.

The second half of the file is the same draft after a human has corrected it:
anchored entries and a pin naming the framework and language, which is what
`promote_key` accepts. `redirect_keys_dir` is how those tests get a destination
that is not the real folder.

Nothing here writes outside the directory a test hands it. `grading_keys/` is
never touched; `test_drafted_key_location.py` and
`test_promote_key_guards.py` are what hold that.
"""

import json
from pathlib import Path

from artifacts.surface import TOOL_CALL, Surface
from grading_keys import (
    GROUND_TRUTH_SUFFIX, KEYS_DIR, MANIFEST_SUFFIX, key_path)
from key_drafting import DRAFTED_KEYS_DIR
from parsing.languages import PYTHON
import fetch_repo
import grading_keys
import key_drafting
import key_store
import promote_key

APP = "some-fetched-app"
COMMIT = "c" * 40
UPSTREAM_URL = "https://example.invalid/owner/some-fetched-app"
COMMIT_DATE = "2026-01-01T00:00:00Z"

# What a fetch leaves beside the tree it cloned, and what a draft is pinned by.
PIN = fetch_repo.manifest(APP, UPSTREAM_URL, COMMIT, COMMIT_DATE)

# One entry carrying every field the drafting prompt asks the model for.
ENTRY = {"id": "K-01", "file": "agent.py", "line": 7, "owasp_id": "LLM06",
         "llm_surface": "TOOL_CALL", "surface_name": "ShellTool", "component": None,
         "detection": "static", "title": "A shell tool", "description": "why"}


def draft_into(keys_dir: Path, entries: tuple[dict, ...] = (ENTRY,),
               pin: dict = PIN) -> Path:
    """Write one drafted key and its pin into a directory; return the key's path."""
    document = key_drafting.key_document(
        APP, list(entries), pin.get("upstream_commit", ""))
    return key_store.write(APP, document, pin, keys_dir)


# --- what a human adds before promoting one -----------------------------------

# The two judgements `key_store.manifest` leaves out on purpose: a fetcher
# cannot make them, so supplying them is part of a human accepting a draft.
FRAMEWORK = "langgraph"
LANGUAGE = "python"

# An anchor is a quotation of the source at the entry's line, read off disk by
# `key_drafting.anchored` and never asked of the model. `ENTRY` carries none,
# because that is the shape the model replies in.
ANCHOR = "tools = [ShellTool()]"
ANCHORED_ENTRY = {**ENTRY, "code_anchor": ANCHOR}

# What the extractor found, recorded beside the entries so a missed surface can
# be told from a bad find. The same surface `ENTRY` names.
SURFACE = Surface(TOOL_CALL, ENTRY["surface_name"], ENTRY["file"], ENTRY["line"],
                  PYTHON, "", "langchain.tools")

# Where a draft sits relative to the keys folder, in the real tree and here.
DRAFTS_NAME = DRAFTED_KEYS_DIR.name


def fit_key(entries: tuple[dict, ...] = (ANCHORED_ENTRY,)) -> dict:
    """A drafted key with nothing left for `key_promotion` to refuse."""
    return key_drafting.key_document(APP, list(entries), COMMIT, [SURFACE])


def fit_pin(**corrections: str) -> dict:
    """A drafted pin with the framework and language a human fills in at promotion."""
    return {**key_store.manifest(APP, PIN), "framework": FRAMEWORK,
            "language": LANGUAGE, **corrections}


def _dump(path: Path, document: dict) -> None:
    """Write one grading document the way `key_store` writes it."""
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def corrected_draft(drafts_dir: Path, key: dict | None = None,
                    pin: dict | None = None) -> Path:
    """Write a draft as a human hands it to `promote_key`; return the key's path.

    Not written through `key_store.write`: that builds the manifest itself and
    drops `framework` and `language`, which is exactly what a human corrects.
    """
    drafts_dir.mkdir(parents=True, exist_ok=True)
    path = key_path(APP, GROUND_TRUTH_SUFFIX, drafts_dir)
    _dump(path, fit_key() if key is None else key)
    _dump(key_path(APP, MANIFEST_SUFFIX, drafts_dir), fit_pin() if pin is None else pin)
    return path


def redirect_keys_dir(monkeypatch, tmp_path: Path) -> Path:
    """Point `grading_keys.KEYS_DIR` at an empty folder under `tmp_path`, and return it.

    Promotion's destination is `KEYS_DIR` itself, and the real one is this
    project's committed evidence -- no test may write into it. `key_path`
    resolves the constant at call time so it can be pointed elsewhere, which is
    the seam `test_drafted_key_pin.py` already promotes through.
    """
    keys_dir = tmp_path / KEYS_DIR.name
    keys_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(grading_keys, "KEYS_DIR", keys_dir)
    return keys_dir


def promote_one_draft(monkeypatch, tmp_path: Path) -> Path:
    """Promote one corrected draft into a temporary keys folder, and return the folder.

    Spelled here because three files hold the promoted pair to the rules a
    shipped key obeys, and they must be talking about the same promotion.
    """
    keys_dir = redirect_keys_dir(monkeypatch, tmp_path)
    drafts_dir = keys_dir / DRAFTS_NAME
    corrected_draft(drafts_dir)
    promote_key.promote(APP, drafts_dir)
    return keys_dir


def promoted_document(keys_dir: Path, suffix: str) -> dict:
    """Read one promoted grading document from where discovery would read it."""
    return json.loads(key_path(APP, suffix, keys_dir).read_text(encoding="utf-8"))
