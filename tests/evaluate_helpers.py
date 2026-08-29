"""Staging a whole scored run under `tmp_path`, for the evaluation entry point's tests.

Three test files drive `evaluate.main()`. Each needs a corpus with a grading
key, a downloaded copy of the app, and one system's artifacts underneath
`<artifacts-dir>/<system>/<app>/`. That setup is spelled once here, so the
per-system layout the tests are about is written down in exactly one place.

Nothing here reads or writes the real `corpus/`: the three lookups that would
are redirected at the temporary tree.
"""

import json
import sys
from pathlib import Path

import pytest

import evaluate
from corpus_paths import (
    GROUND_TRUTH_SUFFIX,
    MANIFEST_SUFFIX,
    app_is_present,
    discover_corpus_apps,
    evidence_path,
)
from evaluation import harness
from evaluation.document import AGENTIC_AUDITOR
from evaluation.harness import EVALUATION_NAME, FINDINGS_NAME, SURFACES_NAME
from evaluation_fixtures import APP, COMMIT, findings_document, grading_key, key_entry, \
    surfaces_document
from findings_fixtures import static_finding

# A second scored system, to prove the layout keeps two of them apart.
OTHER_SYSTEM = "baseline_static_rules"

# The three directories a staged run uses.
CORPUS_DIR_NAME = "corpus"
EVIDENCE_DIR_NAME = "evidence"
ARTIFACTS_DIR_NAME = "artifacts"

# Enough of a manifest to satisfy the fixture check: it must exist and pin a commit.
MANIFEST = {"name": APP, "upstream_commit": COMMIT}


def write_json(path: Path, document: dict) -> None:
    """Write one staged document where the code under test will look for it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def stage_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                 key: dict | None = None) -> None:
    """Point discovery, the download check and the key lookup at a temporary corpus."""
    evidence, corpus = tmp_path / EVIDENCE_DIR_NAME, tmp_path / CORPUS_DIR_NAME
    (corpus / APP).mkdir(parents=True)
    write_json(evidence / f"{APP}{GROUND_TRUTH_SUFFIX}", key or grading_key([key_entry()]))
    write_json(evidence / f"{APP}{MANIFEST_SUFFIX}", MANIFEST)
    monkeypatch.setattr(evaluate, "discover_corpus_apps",
                        lambda: discover_corpus_apps(corpus, evidence))
    monkeypatch.setattr(evaluate, "app_is_present", lambda app: app_is_present(app, corpus))
    monkeypatch.setattr(harness, "evidence_path",
                        lambda app, suffix: evidence_path(app, suffix, evidence))


def stage_artifacts(tmp_path: Path, system: str = AGENTIC_AUDITOR,
                    findings: dict | None = None) -> Path:
    """Write one system's findings and surfaces for the app; return the artifacts root."""
    artifacts_dir = tmp_path / ARTIFACTS_DIR_NAME
    produced = findings if findings is not None else findings_document([static_finding()])
    write_json(artifacts_dir / system / APP / FINDINGS_NAME, produced)
    write_json(artifacts_dir / system / APP / SURFACES_NAME, surfaces_document())
    return artifacts_dir


def run_evaluate(monkeypatch: pytest.MonkeyPatch, artifacts_dir: Path,
                 system: str | None = None) -> int:
    """Run the entry point through argparse, the way a shell would."""
    argv = ["evaluate.py", "--artifacts-dir", str(artifacts_dir)]
    if system is not None:
        argv += ["--system", system]
    monkeypatch.setattr(sys, "argv", argv)
    return evaluate.main()


def read_evaluation(artifacts_dir: Path, system: str = AGENTIC_AUDITOR) -> dict:
    """Read back the evaluation one system's run wrote."""
    return json.loads(
        (artifacts_dir / system / EVALUATION_NAME).read_text(encoding="utf-8"))


def scored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **staging) -> dict:
    """Stage a scorable run, score it, and return the document that was written."""
    stage_corpus(tmp_path, monkeypatch, key=staging.pop("key", None))
    artifacts_dir = stage_artifacts(tmp_path, **staging)
    assert run_evaluate(monkeypatch, artifacts_dir) == 0
    return read_evaluation(artifacts_dir)
