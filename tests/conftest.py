"""Shared test setup: puts the flat modules in `src/` on the import path."""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
CORPUS_DIR = REPO_ROOT / "corpus"

# The two deliberately vulnerable demo apps used as the grading fixtures.
DEMO_APPS = ("vuln-app-1-support-agent", "vuln-app-2-broken-integration")

# src/ is a plain folder of modules, not a package, so it must be importable.
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def read_json(path: Path) -> dict:
    """Read one UTF-8 JSON file and return its object."""
    return json.loads(path.read_text(encoding="utf-8"))


def ground_truth(app: str) -> dict:
    """Return a demo app's ground_truth.json, the grading key for that app."""
    return read_json(CORPUS_DIR / app / "ground_truth.json")


def manifest(app: str) -> dict:
    """Return a demo app's MANIFEST.json, which records its upstream provenance."""
    return read_json(CORPUS_DIR / app / "MANIFEST.json")
