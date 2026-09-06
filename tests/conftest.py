"""Shared test setup: puts the flat modules in `src/` on the import path.

There is no fixture-locating helper here any more. The pinned corpus was
removed on 2026-09-04, so no test reads a third-party tree from a
project-owned path: every test that needs source code writes it into
`tmp_path` itself. What that costs is stated in each re-anchored file.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"

# src/ is a plain folder of modules, not a package, so it must be importable
# before anything below can import from it.
TESTS_DIR = Path(__file__).resolve().parent

# src/ so the modules under test import, and tests/ so the shared helpers next
# to this file are importable from the subfolders that hold the tests.
for directory in (SRC_DIR, TESTS_DIR):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from parsing.extractor import extract_repo  # noqa: E402
from artifacts.surface import surfaces_to_json  # noqa: E402
from keys import key_drafting  # noqa: E402


def scan_to_json(repo_path: str) -> str:
    """Serialise one whole scan, so two separate walks can be compared byte for byte."""
    scan = extract_repo(repo_path)
    return surfaces_to_json(scan.surfaces, scan.skipped)


def read_json(path: Path) -> dict:
    """Read one UTF-8 JSON file and return its object."""
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _drafts_never_reach_the_tracked_folder(tmp_path_factory, monkeypatch):
    """Point drafted grading keys at a temporary folder for every test.

    `grading_keys/` is this project's committed evidence, and
    `key_drafting.DRAFTED_KEYS_DIR` is an absolute path inside it. Any test that
    reaches the drafting stage with a model stubbed to answer JSON would write a
    model-authored answer key into the tree, and a later `git add` would commit
    it as though a human wrote it.

    Only `--draft-key` reaches that stage; until 2026-09-06 every URL run did,
    which is what this fixture was written for and why it stays autouse -- the
    tests at risk are the ones that do not know they are. A test that wants the
    real value imports the name directly, which binds before this runs and is
    therefore unaffected.
    """
    monkeypatch.setattr(key_drafting, "DRAFTED_KEYS_DIR",
                        tmp_path_factory.mktemp("drafts"))
