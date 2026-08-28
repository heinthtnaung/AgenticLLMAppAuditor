"""The Phase 4 join: a produced finding is matched to the grading key it answers.

`SCHEMAS.md` states the rule, so no scorer ever has to parse an id: `file` and
`owasp_id` equal, `line` inside `[line, (line_end or line) + LINE_TOLERANCE]`,
and `surface_kind` / `surface_name` equal where the key names them. The rule
itself lives in `evaluation/grading.py` and is imported here, so this file
certifies the join the Phase 4 scorer really runs rather than a copy of it.
This is the test that shows the phase is gradeable at all -- without it, "one
finding" is a number with nothing on the other side of it.
"""

from artifacts.finding import DETECTIONS
from evaluation.grading import LINE_TOLERANCE, matches_key
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK
from conftest import ground_truth
from dependency_fixtures import LANGGRAPHJS_STARTER, SUPPORT_AGENT, corpus_sbom, js_sbom
from findings_fixtures import corpus_findings

# The two key entries this phase answers today: the undeclared dependency the
# mapping found, and the untrusted input the trace followed to the agent.
GRADED_LLM03 = "VULN1-06"
GRADED_LLM01 = "VULN1-03"

# The rest of the key, which no check reaches yet. Written down rather than
# left implicit: an unanswered entry is a known gap, and Phase 4 scores it as a
# miss whether or not anyone wrote it here.
UNANSWERED = {"VULN1-01", "VULN1-02", "VULN1-04", "VULN1-05"}


def matched_key_ids(finding: dict, app: str) -> set[str]:
    """Return the ids of every key entry a produced finding matches."""
    return {entry["id"] for entry in ground_truth(app)["findings"] if matches_key(finding, entry)}


def support_agent_findings() -> list[dict]:
    """Return every finding the checks produced for the vulnerable app."""
    return corpus_findings(SUPPORT_AGENT, corpus_sbom())["findings"]


def finding_by_rule(rule_id: str) -> dict:
    """Return the one finding a given check produced, selected by rule rather than position.

    By rule, so each test below stays a statement about one check's finding
    whatever else the document comes to hold.
    """
    produced = [f for f in support_agent_findings() if f["rule_id"] == rule_id]
    assert len(produced) == 1, f"expected one {rule_id} finding, got {produced}"
    return produced[0]


def support_agent_finding() -> dict:
    """Return the supply-chain finding, which the mutation tests below vary."""
    return finding_by_rule(SUPPLY_CHAIN_CHECK)


def key_entry(app: str, entry_id: str) -> dict:
    """Return one entry of an app's grading key by its hand-authored id."""
    return next(e for e in ground_truth(app)["findings"] if e["id"] == entry_id)


def test_the_key_still_grades_the_undeclared_dependency() -> None:
    """The join proves something only while the key still records VULN1-06."""
    entry = key_entry(SUPPORT_AGENT, GRADED_LLM03)
    assert (entry["owasp_id"], entry["file"], entry["line"]) == ("LLM03", "utils.py", 75)


def test_the_key_still_grades_the_untrusted_input() -> None:
    """The trace's finding is only worth anything while the key still records VULN1-03."""
    entry = key_entry(SUPPORT_AGENT, GRADED_LLM01)
    assert (entry["owasp_id"], entry["file"], entry["line"]) == ("LLM01", "main.py", 60)


def test_the_supply_chain_finding_matches_the_graded_key_entry() -> None:
    """The undeclared-dependency finding answers VULN1-06, and only it."""
    assert matched_key_ids(support_agent_finding(), SUPPORT_AGENT) == {GRADED_LLM03}


def test_the_traced_finding_matches_the_graded_key_entry() -> None:
    """The untrusted-input finding answers VULN1-03, and only it."""
    assert matched_key_ids(finding_by_rule(TAINT_CHECK), SUPPORT_AGENT) == {GRADED_LLM01}


def test_the_two_produced_findings_answer_two_key_entries() -> None:
    """Together they cover exactly these two, so neither is double-counted in Phase 4."""
    matched = set().union(*(matched_key_ids(f, SUPPORT_AGENT) for f in support_agent_findings()))
    assert matched == {GRADED_LLM01, GRADED_LLM03}


def test_the_rest_of_the_key_is_still_unanswered() -> None:
    """The known gap, stated: four graded entries no check reaches yet.

    It is asserted rather than noted so that a check landing for one of them
    has to update this line, instead of the gap quietly changing size.
    """
    matched = set().union(*(matched_key_ids(f, SUPPORT_AGENT) for f in support_agent_findings()))
    every_id = {entry["id"] for entry in ground_truth(SUPPORT_AGENT)["findings"]}
    assert every_id - matched == UNANSWERED


def test_the_join_uses_the_surface_kind_and_name_the_key_gives() -> None:
    """Both are named on this entry, so both are part of the match."""
    entry = key_entry(SUPPORT_AGENT, GRADED_LLM03)
    finding = support_agent_finding()
    assert finding["surface_kind"] == entry["llm_surface"]
    assert finding["surface_name"] == entry["surface_name"]


def test_a_finding_in_another_file_does_not_match() -> None:
    """Mutation check: the join is only evidence if a wrong location fails it."""
    elsewhere = {**support_agent_finding(), "file": "main.py"}
    assert matched_key_ids(elsewhere, SUPPORT_AGENT) == set()


def test_a_finding_of_another_risk_class_does_not_match() -> None:
    """Classification is what Phase 4 scores, so the owasp id has to agree."""
    misclassified = {**support_agent_finding(), "owasp_id": "LLM06"}
    assert matched_key_ids(misclassified, SUPPORT_AGENT) == set()


def test_a_finding_past_the_line_window_does_not_match() -> None:
    """The tolerance is bounded: four lines below the anchor is a different construct."""
    entry = key_entry(SUPPORT_AGENT, GRADED_LLM03)
    drifted = {**support_agent_finding(), "line": entry["line"] + LINE_TOLERANCE + 1}
    assert matched_key_ids(drifted, SUPPORT_AGENT) == set()


def test_a_finding_at_the_edge_of_the_window_still_matches() -> None:
    """A detector may anchor a few lines below where a human noted the construct."""
    entry = key_entry(SUPPORT_AGENT, GRADED_LLM03)
    drifted = {**support_agent_finding(), "line": entry["line"] + LINE_TOLERANCE}
    assert matched_key_ids(drifted, SUPPORT_AGENT) == {GRADED_LLM03}


def test_the_tool_never_emits_the_keys_own_id() -> None:
    """A tool that writes VULN1-06 hands Phase 4 the answer it was meant to check.

    The whole document is searched, probes included: an id copied into a probe
    record would give the same answer away by a different route.
    """
    document = str(corpus_findings(SUPPORT_AGENT, corpus_sbom()))
    emitted = {entry["id"] for entry in ground_truth(SUPPORT_AGENT)["findings"]
               if entry["id"] in document}
    assert emitted == set()


def test_every_produced_detection_says_what_happened_this_run() -> None:
    """The key's `either` is a property of the class; the tool records only what it did."""
    assert {f["detection"] for f in support_agent_findings()} <= set(DETECTIONS)


def test_the_clean_fixture_produces_nothing_to_join() -> None:
    """Its key is complete, so every produced finding would be a false positive."""
    document = corpus_findings(LANGGRAPHJS_STARTER, js_sbom())
    assert document["findings"] == []
    assert ground_truth(LANGGRAPHJS_STARTER)["findings"] == []
