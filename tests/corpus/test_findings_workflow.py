"""What the audit loop really plans and runs over the two fixtures covered here.

The document-level results are asserted in test_findings_produced.py and
test_findings_traced.py. What is asserted here is the loop that now produces
them: how many steps it took, which checks it chose, in what order, and that
what reaches `coverage.checks_run` is that record rather than a list written
beside it.

The two findings are checked against the grading key's own entries -- VULN1-06
and VULN1-03 -- so the expected file and line come from the key rather than
from this file.
"""

from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK
from checks.workflow import MAX_STEPS, audit
from conftest import ground_truth
from dependency_fixtures import LANGGRAPHJS_STARTER, SUPPORT_AGENT, corpus_sbom, js_sbom
from findings_fixtures import corpus_findings, corpus_inputs

# The order the planner is handed on a Python app with a mapping to read.
PYTHON_APP_PLAN = [PERMISSION_CHECK, SUPPLY_CHAIN_CHECK, TAINT_CHECK]

# The JavaScript app has no Python to trace, so the trace is never planned.
JS_APP_PLAN = [PERMISSION_CHECK, SUPPLY_CHAIN_CHECK]

# Sources the trace could not follow on the Python app, counted by hand and
# listed one by one in test_findings_traced.py.
UNFOLLOWED_SOURCE_COUNT = 9


def audit_support_agent() -> dict:
    """Run the loop over the vulnerable Python app and return the state it built."""
    return audit(*corpus_inputs(SUPPORT_AGENT, corpus_sbom()), PYTHON_APP_PLAN)


def audit_clean_fixture() -> dict:
    """Run the loop over the JavaScript app the grading key calls clean."""
    return audit(*corpus_inputs(LANGGRAPHJS_STARTER, js_sbom()), JS_APP_PLAN)


def graded_finding(finding_id: str) -> dict:
    """Return one recorded finding from the Python app's grading key."""
    recorded = [f for f in ground_truth(SUPPORT_AGENT)["findings"] if f["id"] == finding_id]
    assert len(recorded) == 1, f"{finding_id} is not in the grading key exactly once"
    return recorded[0]


def test_the_planner_runs_every_check_the_python_app_gave_it_something_to_do() -> None:
    """Three checks, three steps, nothing left unrun."""
    state = audit_support_agent()
    assert state["checks_run"] == PYTHON_APP_PLAN
    assert state["steps"] == 3 and state["remaining"] == []


def test_a_real_audit_finishes_far_inside_the_step_cap() -> None:
    """The cap is a backstop: it never truncates an app the auditor actually audits."""
    assert audit_support_agent()["steps"] < MAX_STEPS


def test_the_two_findings_arrive_in_the_order_their_checks_ran() -> None:
    """Supply chain ran second and the trace third, and the state reads that way."""
    findings = audit_support_agent()["findings"]
    assert [finding.owasp_id for finding in findings] == ["LLM03", "LLM01"]
    assert [finding.rule_id for finding in findings] == [SUPPLY_CHAIN_CHECK, TAINT_CHECK]


def test_the_supply_chain_finding_sits_where_the_key_records_vuln1_06() -> None:
    """The undeclared PyYAML import, at the file and line the grading key names."""
    graded = graded_finding("VULN1-06")
    finding = audit_support_agent()["findings"][0]
    assert (finding.file, finding.line) == (graded["file"], graded["line"])
    assert finding.owasp_id == graded["owasp_id"]


def test_the_traced_finding_sits_where_the_key_records_vuln1_03() -> None:
    """The chat input reaching the agent, anchored on the line the key names."""
    graded = graded_finding("VULN1-03")
    finding = audit_support_agent()["findings"][1]
    assert (finding.file, finding.line) == (graded["file"], graded["line"])
    assert finding.owasp_id == graded["owasp_id"]


def test_the_gaps_the_trace_could_not_follow_survive_the_loop() -> None:
    """Nine inconclusive probes reach the final state, beside the two findings."""
    assert len(audit_support_agent()["probes"]) == UNFOLLOWED_SOURCE_COUNT


def test_the_document_reports_the_checks_the_loop_actually_ran() -> None:
    """`coverage.checks_run` is the loop's record, sorted, not a second list of its own."""
    document = corpus_findings(SUPPORT_AGENT, corpus_sbom())
    assert document["coverage"]["checks_run"] == sorted(audit_support_agent()["checks_run"])


def test_the_clean_fixture_runs_the_two_checks_that_could_examine_it() -> None:
    """Two steps, no findings and no probes: the zero is a result the loop reached."""
    state = audit_clean_fixture()
    assert state["checks_run"] == JS_APP_PLAN and state["steps"] == 2
    assert (state["findings"], state["probes"]) == ([], [])


def test_the_trace_is_never_planned_for_the_javascript_app() -> None:
    """It reads an `ast` tree, so planning it there would claim a clean run it never made."""
    assert TAINT_CHECK not in audit_clean_fixture()["checks_run"]


def test_two_runs_of_the_loop_agree_on_what_ran_and_what_was_found() -> None:
    """The planner is deterministic, which is what lets the artifacts be byte-identical."""
    first, second = audit_support_agent(), audit_support_agent()
    assert first["checks_run"] == second["checks_run"]
    assert [f.id for f in first["findings"]] == [f.id for f in second["findings"]]
