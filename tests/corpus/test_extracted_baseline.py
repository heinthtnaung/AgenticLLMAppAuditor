"""The extractor's output has not changed unexpectedly since the baseline was taken.

This is regression protection, NOT validation. Each baseline is generated from
the tool's own output, so it can only detect change -- it can never show the
tool is right. Accuracy is measured against ground_truth.json instead.
"""

import json

import pytest
from conftest import BASELINE_SUFFIX, CORPUS_APPS, CORPUS_DIR, evidence_path, require_corpus
from parsing.extractor import extract_repo

def baseline(app: str) -> dict:
    """Read one app's recorded extractor output."""
    return json.loads(evidence_path(app, BASELINE_SUFFIX).read_text(encoding="utf-8"))


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_baseline_is_marked_as_tool_derived(app: str) -> None:
    """The file must say what it is, so nobody mistakes it for a grading key."""
    require_corpus(app)
    assert baseline(app)["source"] == "tool_derived"


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_extractor_output_matches_the_baseline(app: str) -> None:
    """Every surface in the baseline is still found, and no new one appeared."""
    require_corpus(app)
    recorded = {(s["file"], s["line"], s["kind"], s["name"]) for s in baseline(app)["surfaces"]}
    found = {(s.file, s.line, s.kind, s.name) for s in extract_repo(str(CORPUS_DIR / app))}
    assert found - recorded == set(), "new surfaces appeared; re-record the baseline if intended"
    assert recorded - found == set(), "surfaces disappeared; this is a regression unless intended"


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_baseline_count_matches_its_own_list(app: str) -> None:
    """The stated count and the list cannot disagree."""
    require_corpus(app)
    recorded = baseline(app)
    assert recorded["surface_count"] == len(recorded["surfaces"])
