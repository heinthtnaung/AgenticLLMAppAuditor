"""The comparison Phase 4 exists to produce, pinned so the write-up cannot drift.

Three systems, one corpus, one join rule, the harness unmodified. Every number
below was read off a real run; they are written down rather than recomputed,
so a change in any system fails this file instead of quietly moving the table
an examiner reads.

| System                  | Recall on the vulnerable app | False positives, clean apps |
|-------------------------|------------------------------|-----------------------------|
| `agentic_auditor`       | 2 of 6                       | 0 and 0                     |
| `baseline_static_rules` | 5 of 6                       | 0 and 1                     |
| `baseline_sbom_only`    | 0 of 6                       | 75 and 112                  |

The grep baseline beats the auditor on recall, 5 to 2. That is reported first
because a comparison that only shows wins is not evidence.
"""

import json

import pytest

from artifacts.surface import surfaces_to_json
from baseline_fixtures import require_syft
from conftest import app_path, ground_truth, require_corpus
from dependency_fixtures import (
    LANGGRAPHJS_STARTER,
    REACT_AGENT,
    SUPPORT_AGENT,
    corpus_sbom,
)
from evaluation.document import AGENTIC_AUDITOR
from evaluation.scorer import score_app
from findings_fixtures import corpus_findings
from parsing.extractor import extract_repo
from run_baseline import SBOM_ONLY, STATIC_RULES, build_documents

KEY_FINDING_COUNT = 6

# Recall on the vulnerable app, per system. The headline of the whole phase.
AUDITOR_TRUE_POSITIVES = 2
STATIC_RULES_TRUE_POSITIVES = 5
SBOM_ONLY_TRUE_POSITIVES = 0

# False positives on the two clean apps, whose keys claim completeness. The
# auditor's row of this table is pinned in `tests/corpus/test_evaluation_corpus.py`,
# where its own run is scored; it is not restated here.
CLEAN_APP_FALSE_POSITIVES = {
    STATIC_RULES: {LANGGRAPHJS_STARTER: 0, REACT_AGENT: 1},
    SBOM_ONLY: {LANGGRAPHJS_STARTER: 75, REACT_AGENT: 112},
}

# What each system produced on the vulnerable app, whose key claims no completeness.
PRODUCED_ON_THE_VULNERABLE_APP = {
    AGENTIC_AUDITOR: 2, STATIC_RULES: 6, SBOM_ONLY: 3,
}

# The auditor loses two entries to classes it does not cover; Baseline A has a
# crude rule for each. Its coverage is *wider*, which is why it wins.
AUDITOR_CLASSES = ["LLM01", "LLM03", "LLM06"]
STATIC_RULES_ONLY_CLASSES = {"LLM02", "AUDITABILITY"}


def scan_document(app: str) -> dict:
    """Return the app's surfaces.json as the scorer reads it, from a real extraction."""
    scan = extract_repo(str(app_path(app)))
    return json.loads(surfaces_to_json(scan.surfaces, scan.skipped))


def score_baseline(system: str, app: str) -> dict:
    """Run one baseline over one corpus app and score it through the unmodified harness."""
    require_corpus(app)
    findings, surfaces = build_documents(system, str(app_path(app)))
    return score_app(app, ground_truth(app), json.loads(findings), json.loads(surfaces))


@pytest.fixture(scope="module")
def auditor_on_the_vulnerable_app() -> dict:
    """Score this project's own output, the way `test_evaluation_corpus.py` does."""
    require_corpus(SUPPORT_AGENT)
    return score_app(SUPPORT_AGENT, ground_truth(SUPPORT_AGENT),
                     corpus_findings(SUPPORT_AGENT, corpus_sbom()), scan_document(SUPPORT_AGENT))


@pytest.fixture(scope="module")
def static_rules_on_the_vulnerable_app() -> dict:
    """Score Baseline A on the app that grades six findings."""
    return score_baseline(STATIC_RULES, SUPPORT_AGENT)


@pytest.fixture(scope="module")
def sbom_only_on_the_vulnerable_app() -> dict:
    """Score Baseline B, which needs the real generator it is a baseline for."""
    require_syft()
    return score_baseline(SBOM_ONLY, SUPPORT_AGENT)


def test_the_auditor_answers_two_of_the_six_graded_findings(
        auditor_on_the_vulnerable_app) -> None:
    """The number this project reports about itself, restated beside its rivals."""
    scored = auditor_on_the_vulnerable_app
    assert (scored["true_positives"], scored["key_finding_count"]) == (
        AUDITOR_TRUE_POSITIVES, KEY_FINDING_COUNT)


def test_the_grep_baseline_answers_five_and_beats_the_auditor(
        static_rules_on_the_vulnerable_app, auditor_on_the_vulnerable_app) -> None:
    """5 to 2, on the same key, through the same harness. The headline result."""
    assert static_rules_on_the_vulnerable_app["true_positives"] == STATIC_RULES_TRUE_POSITIVES
    assert (static_rules_on_the_vulnerable_app["true_positives"]
            > auditor_on_the_vulnerable_app["true_positives"])


def test_the_sbom_baseline_answers_none_of_them(sbom_only_on_the_vulnerable_app) -> None:
    """Zero, and its ceiling was zero: it never had a line to answer with."""
    scored = sbom_only_on_the_vulnerable_app
    assert (scored["true_positives"], scored["key_finding_count"]) == (
        SBOM_ONLY_TRUE_POSITIVES, KEY_FINDING_COUNT)


def test_the_auditor_loses_ground_it_never_entered(auditor_on_the_vulnerable_app) -> None:
    """Two of its four misses are classes no check of its own covers at all."""
    reasons = [miss["reason"] for miss in auditor_on_the_vulnerable_app["misses"]]
    assert reasons.count("no_check_for_risk_class") == 2


def test_the_grep_baseline_checks_two_classes_the_auditor_does_not() -> None:
    """LLM02 and AUDITABILITY. Wider coverage, crudely done, is why the baseline wins."""
    require_corpus(SUPPORT_AGENT)
    findings, _ = build_documents(STATIC_RULES, str(app_path(SUPPORT_AGENT)))
    baseline_classes = set(json.loads(findings)["coverage"]["risk_classes_checked"])
    auditor_classes = set(
        corpus_findings(SUPPORT_AGENT, corpus_sbom())["coverage"]["risk_classes_checked"])
    assert auditor_classes == set(AUDITOR_CLASSES)
    assert STATIC_RULES_ONLY_CLASSES <= baseline_classes - auditor_classes


@pytest.mark.parametrize("app", (LANGGRAPHJS_STARTER, REACT_AGENT))
def test_the_grep_baselines_false_positives_on_the_clean_apps(app) -> None:
    """One false positive, on the Python template, where the auditor stays quiet."""
    scored = score_baseline(STATIC_RULES, app)
    assert scored["false_positives"] == CLEAN_APP_FALSE_POSITIVES[STATIC_RULES][app]
    assert scored["precision_reportable"] is True


@pytest.mark.parametrize("app", (LANGGRAPHJS_STARTER, REACT_AGENT))
def test_the_sbom_baseline_reports_every_component_as_a_false_positive(app) -> None:
    """187 between them: presence is not risk, and without advisories that is all it has."""
    require_syft()
    scored = score_baseline(SBOM_ONLY, app)
    assert scored["false_positives"] == CLEAN_APP_FALSE_POSITIVES[SBOM_ONLY][app]


def test_each_system_produced_what_the_table_says_on_the_vulnerable_app(
        auditor_on_the_vulnerable_app, static_rules_on_the_vulnerable_app,
        sbom_only_on_the_vulnerable_app) -> None:
    """The produced counts are the denominators; the table is unreadable without them."""
    produced = {
        AGENTIC_AUDITOR: auditor_on_the_vulnerable_app["produced_finding_count"],
        STATIC_RULES: static_rules_on_the_vulnerable_app["produced_finding_count"],
        SBOM_ONLY: sbom_only_on_the_vulnerable_app["produced_finding_count"],
    }
    assert produced == PRODUCED_ON_THE_VULNERABLE_APP


def test_no_system_can_report_a_false_positive_on_the_vulnerable_app(
        auditor_on_the_vulnerable_app, static_rules_on_the_vulnerable_app,
        sbom_only_on_the_vulnerable_app) -> None:
    """Its key claims no completeness, so `null` is the answer for all three alike."""
    for scored in (auditor_on_the_vulnerable_app, static_rules_on_the_vulnerable_app,
                   sbom_only_on_the_vulnerable_app):
        assert scored["false_positives"] is None
