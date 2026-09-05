"""Staging a whole scored run under `tmp_path`, for the evaluation entry point's tests.

Three test files drive `evaluate.main()`. Each needs a grading key and one
system's artifacts underneath `<artifacts-dir>/<system>/<app>/`. That setup is
spelled once here, so the per-system layout the tests are about is written down
in exactly one place.

The key is written by these helpers, not read from the repository: this project
ships no grading key, and a key is hand-placed input in any case. Nothing here
touches the real `grading_keys/` -- both the entry point and the harness take a
`keys_dir`, so the temporary tree is passed in as an argument rather than
patched over a module global.
"""

import json
import sys
from pathlib import Path

import pytest

import evaluate
from evaluation.document import AGENTIC_AUDITOR
from evaluation.harness import EVALUATION_NAME, FINDINGS_NAME, SURFACES_NAME
from evaluation_fixtures import APP, COMMIT, findings_document, grading_key, key_entry, \
    surfaces_document
from findings_fixtures import static_finding
from grading_keys import GROUND_TRUTH_SUFFIX, MANIFEST_SUFFIX

# A second scored system, to prove the layout keeps two of them apart.
OTHER_SYSTEM = "baseline_static_rules"

# The two directories a staged run uses.
KEYS_DIR_NAME = "grading_keys"
ARTIFACTS_DIR_NAME = "artifacts"

# Enough of a manifest to satisfy the discovery check: it must exist and pin a commit.
MANIFEST = {"name": APP, "upstream_commit": COMMIT}


def write_json(path: Path, document: dict) -> None:
    """Write one staged document where the code under test will look for it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def stage_keys(tmp_path: Path, key: dict | None = None) -> Path:
    """Write one app's grading key and its pin into a temporary keys directory."""
    keys_dir = tmp_path / KEYS_DIR_NAME
    write_json(keys_dir / f"{APP}{GROUND_TRUTH_SUFFIX}", key or grading_key([key_entry()]))
    write_json(keys_dir / f"{APP}{MANIFEST_SUFFIX}", MANIFEST)
    return keys_dir


def stage_empty_keys(tmp_path: Path) -> Path:
    """Create a keys directory holding no key at all: this project's normal state."""
    keys_dir = tmp_path / KEYS_DIR_NAME
    keys_dir.mkdir()
    return keys_dir


def stage_artifacts(tmp_path: Path, system: str = AGENTIC_AUDITOR,
                    findings: dict | None = None) -> Path:
    """Write one system's findings and surfaces for the app; return the artifacts root."""
    artifacts_dir = tmp_path / ARTIFACTS_DIR_NAME
    produced = findings if findings is not None else findings_document([static_finding()])
    write_json(artifacts_dir / system / APP / FINDINGS_NAME, produced)
    write_json(artifacts_dir / system / APP / SURFACES_NAME, surfaces_document())
    return artifacts_dir


def run_evaluate(monkeypatch: pytest.MonkeyPatch, artifacts_dir: Path,
                 system: str | None = None, keys_dir: Path | None = None) -> int:
    """Run the entry point through argparse, the way a shell would."""
    argv = ["evaluate.py", "--artifacts-dir", str(artifacts_dir)]
    if system is not None:
        argv += ["--system", system]
    if keys_dir is not None:
        argv += ["--keys-dir", str(keys_dir)]
    monkeypatch.setattr(sys, "argv", argv)
    return evaluate.main()


def read_evaluation(artifacts_dir: Path, system: str = AGENTIC_AUDITOR) -> dict:
    """Read back the evaluation one system's run wrote."""
    return json.loads(
        (artifacts_dir / system / EVALUATION_NAME).read_text(encoding="utf-8"))


def scored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **staging) -> dict:
    """Stage a scorable run, score it, and return the document that was written."""
    keys_dir = stage_keys(tmp_path, key=staging.pop("key", None))
    artifacts_dir = stage_artifacts(tmp_path, **staging)
    assert run_evaluate(monkeypatch, artifacts_dir, keys_dir=keys_dir) == 0
    return read_evaluation(artifacts_dir)
