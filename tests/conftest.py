"""Shared test setup: puts the flat modules in `src/` on the import path.

There is no fixture-locating helper here any more. The pinned corpus was
removed on 2026-09-04, so no test reads a third-party tree from a
project-owned path: every test that needs source code writes it into
`tmp_path` itself. What that costs is stated in each re-anchored file.
"""

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

from parsing.extractor import extract_repo  # noqa: E402
from artifacts.surface import surfaces_to_json  # noqa: E402


def scan_to_json(repo_path: str) -> str:
    """Serialise one whole scan, so two separate walks can be compared byte for byte."""
    scan = extract_repo(repo_path)
    return surfaces_to_json(scan.surfaces, scan.skipped)


def read_json(path: Path) -> dict:
    """Read one UTF-8 JSON file and return its object."""
    return json.loads(path.read_text(encoding="utf-8"))
