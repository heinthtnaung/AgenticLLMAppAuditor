"""Shared test setup: puts the flat modules in `src/` on the import path."""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
CORPUS_DIR = REPO_ROOT / "corpus"

GROUND_TRUTH_NAME = "ground_truth.json"

# The ground_truth.json schema this suite knows how to read.
GROUND_TRUTH_SCHEMA_VERSION = 2


def discover_corpus_apps(corpus_dir: Path = CORPUS_DIR) -> tuple[str, ...]:
    """Find every corpus app that ships a ground_truth.json, so adding one needs no edit here."""
    apps = sorted(path.parent.name for path in corpus_dir.glob(f"*/{GROUND_TRUTH_NAME}"))
    if not apps:
        raise RuntimeError(
            f"no corpus app with a {GROUND_TRUTH_NAME} under {corpus_dir}. "
            "The grading fixtures are missing, so the suite would test nothing."
        )
    return tuple(apps)


# Every audited fixture found on disk: the vulnerable demo apps and the clean
# open-source template used to measure false positives.
CORPUS_APPS = discover_corpus_apps()

# src/ is a plain folder of modules, not a package, so it must be importable.
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def read_json(path: Path) -> dict:
    """Read one UTF-8 JSON file and return its object."""
    return json.loads(path.read_text(encoding="utf-8"))


def ground_truth(app: str) -> dict:
    """Return a corpus app's ground_truth.json, the grading key for that app."""
    return read_json(CORPUS_DIR / app / "ground_truth.json")


def manifest(app: str) -> dict:
    """Return a corpus app's MANIFEST.json, which records its upstream provenance."""
    return read_json(CORPUS_DIR / app / "MANIFEST.json")
