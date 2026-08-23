"""Shared test setup: puts the flat modules in `src/` on the import path."""

import json
import sys
from pathlib import Path

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

import pytest  # noqa: E402

from corpus_paths import (  # noqa: E402  (import must follow the sys.path line)
    BASELINE_SUFFIX,
    DOWNLOAD_HINT,
    app_is_present,
    CORPUS_DIR,
    EVIDENCE_DIR,
    GROUND_TRUTH_SUFFIX,
    MANIFEST_SUFFIX,
    app_path,
    discover_corpus_apps,
    evidence_path,
)

# The ground_truth.json schema this suite knows how to read.
GROUND_TRUTH_SCHEMA_VERSION = 2

# The fixtures, found on disk rather than listed here.
CORPUS_APPS = discover_corpus_apps()


def read_json(path: Path) -> dict:
    """Read one UTF-8 JSON file and return its object."""
    return json.loads(path.read_text(encoding="utf-8"))


def ground_truth(app: str) -> dict:
    """Return a corpus app's grading key."""
    return read_json(evidence_path(app, GROUND_TRUTH_SUFFIX))


def manifest(app: str) -> dict:
    """Return a corpus app's manifest, which records its upstream provenance."""
    return read_json(evidence_path(app, MANIFEST_SUFFIX))


def require_corpus(app: str) -> None:
    """Skip a test when the audited app has not been downloaded.

    The source is third-party and is not committed, so its absence is normal.
    The skip is visible in the summary and names where to look, so a run with
    no app can never be mistaken for a passing one.
    """
    if not app_is_present(app):
        pytest.skip(f"{app}: {DOWNLOAD_HINT}")
