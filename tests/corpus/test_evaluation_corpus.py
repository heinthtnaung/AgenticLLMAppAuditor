"""What the auditor really scores on the corpus, asserted as measured numbers.

Every figure here was read off a real run over the two fixtures and their real
grading keys. They are written down rather than recomputed in the test, so a
check that starts finding one more thing -- or one thing less -- fails this
file instead of quietly moving the result the write-up quotes.
"""

import json

import pytest

from artifacts.surface import surfaces_to_json
from conftest import app_path, ground_truth, require_corpus
from dependency_fixtures import LANGGRAPHJS_STARTER, SUPPORT_AGENT, corpus_sbom, js_sbom
from evaluation.document import build_evaluation
from evaluation.scorer import score_app
from evaluation_fixtures import every_value
from findings_fixtures import corpus_findings
from parsing.extractor import extract_repo

# What the two checks answer today, and what the other four misses are for.
MATCHED_KEY_IDS = ["VULN1-03", "VULN1-06"]
MISS_REASONS = {
    "VULN1-01": "checked_and_silent",
    "VULN1-02": "checked_and_silent",
    "VULN1-04": "no_check_for_risk_class",
    "VULN1-05": "no_check_for_risk_class",
}

# The classes the run examined, and the two the corpus grades that it cannot.
CHECKED_CLASSES = ["LLM01", "LLM03", "LLM06"]
UNCHECKED_CLASSES = ["LLM02", "AUDITABILITY"]

# Everything that bounds the vulnerable app's numbers, measured not chosen.
SUPPORT_AGENT_QUALIFICATIONS = [
    "advisory_data_not_ingested", "expected_surfaces_not_complete",
    "findings_not_complete", "key_ai_drafted", "model_disabled", "small_sample",
    "unresolved_components",
]


def scan_document(app: str) -> dict:
    """Return the app's surfaces.json as the scorer reads it, from a real extraction."""
    scan = extract_repo(str(app_path(app)))
    return json.loads(surfaces_to_json(scan.surfaces, scan.skipped))


def score(app: str, sbom: dict) -> dict:
    """Score one corpus app against its own grading key."""
    return score_app(app, ground_truth(app), corpus_findings(app, sbom), scan_document(app))


@pytest.fixture(scope="module")
def support_agent() -> dict:
    """Score the vulnerable fixture once and share it across the tests below."""
    require_corpus(SUPPORT_AGENT)
    return score(SUPPORT_AGENT, corpus_sbom())


@pytest.fixture(scope="module")
def langgraphjs_starter() -> dict:
    """Score the clean fixture once and share it across the tests below."""
    require_corpus(LANGGRAPHJS_STARTER)
    return score(LANGGRAPHJS_STARTER, js_sbom())


@pytest.fixture(scope="module")
def evaluation(support_agent: dict, langgraphjs_starter: dict) -> dict:
    """The whole evaluation document for the corpus, which is what Phase 4 publishes."""
    return build_evaluation([support_agent, langgraphjs_starter])


def test_the_vulnerable_app_scores_two_of_its_six_graded_findings(support_agent: dict) -> None:
    """Measured: two answered, four missed, out of a key that grades six."""
    assert (support_agent["true_positives"], support_agent["false_negatives"]) == (2, 4)
    assert support_agent["key_finding_count"] == 6


def test_the_two_answered_entries_are_the_supply_chain_and_the_traced_input(
        support_agent: dict) -> None:
    """Named, so a check that starts answering a different entry is not silently equal."""
    assert support_agent["matched_key_ids"] == MATCHED_KEY_IDS


def test_its_false_positives_are_null_rather_than_zero(support_agent: dict) -> None:
    """Its key does not claim to list every finding, so the count is undefined."""
    assert support_agent["false_positives"] is None
    assert support_agent["findings_complete"] is False


def test_neither_produced_finding_is_left_unmatched(support_agent: dict) -> None:
    """Both findings answer a graded entry, so nothing is unaccounted for."""
    assert support_agent["unmatched_finding_ids"] == []
    assert support_agent["produced_finding_count"] == 2


def test_each_of_its_four_misses_carries_the_reason_it_was_missed(
        support_agent: dict) -> None:
    """Two classes no check covers, and two the checks looked at and stayed silent about."""
    reported = {miss["key_id"]: miss["reason"] for miss in support_agent["misses"]}
    assert reported == MISS_REASONS


def test_the_two_uncovered_classes_are_absent_from_what_the_run_checked() -> None:
    """The reason is derived from this list, so the list is asserted beside it."""
    require_corpus(SUPPORT_AGENT)
    checked = corpus_findings(SUPPORT_AGENT, corpus_sbom())["coverage"]["risk_classes_checked"]
    assert checked == CHECKED_CLASSES
    assert [risk for risk in UNCHECKED_CLASSES if risk in checked] == []


def test_the_probe_that_gave_up_is_reported_beside_the_sql_miss(support_agent: dict) -> None:
    """VULN1-04 has two facts against it: no check for LLM02, and a trace that stopped."""
    sql_miss = next(m for m in support_agent["misses"] if m["key_id"] == "VULN1-04")
    assert sql_miss["probe_reason"] == "trace_left_static_analysis"


def test_the_silent_misses_report_no_probe_reason(support_agent: dict) -> None:
    """Nothing was attempted on those two, and the record must not imply otherwise."""
    silent = [m for m in support_agent["misses"] if m["reason"] == "checked_and_silent"]
    assert [m["probe_reason"] for m in silent] == [None, None]


def test_its_recall_is_reportable_and_its_precision_is_not(support_agent: dict) -> None:
    """The gate that keeps the incomplete key out of every precision number."""
    assert support_agent["recall_reportable"] is True
    assert support_agent["precision_reportable"] is False


def test_its_numbers_carry_all_seven_measured_qualifications(support_agent: dict) -> None:
    """Listed in full: a qualification silently dropped is a number quoted too widely."""
    assert support_agent["qualifications"] == SUPPORT_AGENT_QUALIFICATIONS


def test_the_clean_app_finds_nothing_and_misses_nothing(langgraphjs_starter: dict) -> None:
    """Its key grades nothing, so zero findings is the right answer, not an empty one."""
    assert (langgraphjs_starter["true_positives"],
            langgraphjs_starter["false_negatives"],
            langgraphjs_starter["false_positives"]) == (0, 0, 0)


def test_the_clean_apps_precision_is_reportable_and_its_recall_is_not(
        langgraphjs_starter: dict) -> None:
    """Zero of zero found is not full recall; a complete key with none wrong is precision."""
    assert langgraphjs_starter["precision_reportable"] is True
    assert langgraphjs_starter["recall_reportable"] is False


def test_recall_rests_on_the_vulnerable_app_alone(evaluation: dict) -> None:
    """Pooled counts with the app named, so the sample size travels with them."""
    recall = evaluation["totals"]["recall"]
    assert recall["apps_included"] == [SUPPORT_AGENT]
    assert (recall["true_positives"], recall["false_negatives"]) == (2, 4)
    assert recall["key_finding_count"] == 6


def test_precision_rests_on_the_clean_app_alone(evaluation: dict) -> None:
    """The other half of the split that makes an F1 meaningless on this corpus."""
    precision = evaluation["totals"]["precision"]
    assert precision["apps_included"] == [LANGGRAPHJS_STARTER]
    assert (precision["true_positives"], precision["false_positives"]) == (0, 0)
    assert precision["produced_finding_count"] == 0


def test_f1_is_refused_on_this_corpus_with_its_reason(evaluation: dict) -> None:
    """No app supports both, so the harmonic mean would be about no system."""
    assert evaluation["totals"]["f1_reportable"] is False
    assert evaluation["totals"]["f1_blocked_reason"] == "no app supports both precision and recall"


def test_the_published_document_holds_no_float(evaluation: dict) -> None:
    """The real artifact, not a fixture: no percentage can be copied out of it."""
    document = json.loads(json.dumps(evaluation))
    assert [value for value in every_value(document) if isinstance(value, float)] == []
