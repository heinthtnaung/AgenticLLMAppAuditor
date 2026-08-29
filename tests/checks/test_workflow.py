"""The audit loop's shared state: what the planner runs, in what order, and what it keeps.

The planner picks the next check over one state object, and every check appends
to that state rather than replacing it. Both halves are asserted here, because a
reducer that silently overwrote would still produce a plausible document -- one
holding only the last check's results, with nothing to show the earlier ones
were lost.

The step cap that bounds the loop is in test_workflow_cap.py, and the line
between planning a check and deciding a finding is in test_workflow_scope.py.
"""

from pathlib import Path

import pytest

from artifacts.finding import INCONCLUSIVE
from artifacts.mapping import USED_BUT_UNDECLARED
from artifacts.surface import DATA_SOURCE, TOOL_CALL, Surface
from checks import workflow
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK
from parsing.languages import PYTHON

# One surface each check can act on: a privileged tool for the permission
# check, and the surface the mapping below reports as an undeclared package.
TOOL_SURFACE = Surface(TOOL_CALL, "ShellTool", "agent.py", 12, PYTHON, "tool", "langchain.tools")
DATA_SURFACE = Surface(DATA_SOURCE, "yaml.load", "utils.py", 75, PYTHON, "yaml read", "yaml")

MAPPING = {
    "entries": [{
        "surface_id": DATA_SURFACE.id,
        "reason": USED_BUT_UNDECLARED,
        "component_name": "pyyaml",
    }],
}

# A data source the file never binds to a name: the trace cannot follow it, so
# the check returns a probe and no finding. That is the only check of the three
# that produces a probe, which is what makes it useful for the reducer test.
UNBOUND_FILE = "app.py"
UNBOUND_SOURCE = 'st.chat_input("ask")\n'
UNBOUND_SURFACE = Surface(DATA_SOURCE, "st.chat_input", UNBOUND_FILE, 1, PYTHON, "user input")

BOTH_STATIC_CHECKS = [PERMISSION_CHECK, SUPPLY_CHAIN_CHECK]


def run_audit(repo: Path, plan_order: list[str], surfaces: tuple = (TOOL_SURFACE, DATA_SURFACE),
              mapping: dict | None = MAPPING) -> dict:
    """Run the workflow over a repository with the given plan, and return its final state."""
    return workflow.audit(str(repo), list(surfaces), mapping, list(plan_order))


def repo_with_unbound_source(tmp_path: Path) -> Path:
    """Write the one Python file the taint check can read, holding a source it cannot follow."""
    (tmp_path / UNBOUND_FILE).write_text(UNBOUND_SOURCE, encoding="utf-8")
    return tmp_path


def test_the_planner_runs_every_check_it_was_given(tmp_path) -> None:
    """Two planned checks, both run, and nothing left outstanding."""
    state = run_audit(tmp_path, BOTH_STATIC_CHECKS)
    assert state["checks_run"] == BOTH_STATIC_CHECKS
    assert state["remaining"] == []


def test_checks_run_records_the_order_the_planner_ran_them(tmp_path) -> None:
    """Reversing the plan reverses the record, so the order is the plan's rather than a constant."""
    state = run_audit(tmp_path, list(reversed(BOTH_STATIC_CHECKS)))
    assert state["checks_run"] == [SUPPLY_CHAIN_CHECK, PERMISSION_CHECK]


def test_one_planner_step_is_taken_for_each_check(tmp_path) -> None:
    """The step count is what the cap is measured against, so it counts checks, not nodes."""
    assert run_audit(tmp_path, BOTH_STATIC_CHECKS)["steps"] == 2


def test_both_checks_contribute_their_findings(tmp_path) -> None:
    """The reducer appends: the first check's finding survives the second check running."""
    findings = run_audit(tmp_path, BOTH_STATIC_CHECKS)["findings"]
    assert sorted(finding.rule_id for finding in findings) == sorted(BOTH_STATIC_CHECKS)


def test_findings_arrive_in_the_order_the_checks_ran(tmp_path) -> None:
    """Appending in run order is what makes the state readable as a record of the plan."""
    findings = run_audit(tmp_path, list(reversed(BOTH_STATIC_CHECKS)))["findings"]
    assert [finding.rule_id for finding in findings] == [SUPPLY_CHAIN_CHECK, PERMISSION_CHECK]


def test_a_later_check_does_not_replace_an_earlier_ones_probes(tmp_path) -> None:
    """The trace runs first and the silent check second, so an overwriting reducer would show."""
    repo = repo_with_unbound_source(tmp_path)
    state = run_audit(repo, [TAINT_CHECK, PERMISSION_CHECK],
                      surfaces=(UNBOUND_SURFACE, TOOL_SURFACE), mapping=None)
    assert len(state["probes"]) == 1
    assert state["probes"][0].outcome == INCONCLUSIVE


def test_a_check_that_found_nothing_is_still_recorded_as_having_run(tmp_path) -> None:
    """Silence is a result only because the state names the check that produced it."""
    state = run_audit(tmp_path, [PERMISSION_CHECK], surfaces=(DATA_SURFACE,), mapping=None)
    assert state["findings"] == []
    assert state["checks_run"] == [PERMISSION_CHECK]


def test_an_empty_plan_returns_the_state_the_audit_started_from(tmp_path) -> None:
    """No check had anything to examine, so nothing ran and nothing is claimed."""
    state = run_audit(tmp_path, [])
    assert state["steps"] == 0
    assert (state["checks_run"], state["findings"], state["probes"]) == ([], [], [])


def refuse_to_build() -> object:
    """Stand in for the graph builder, so a call to it fails the test that forbade one."""
    raise AssertionError("the graph was built for a plan holding nothing to run")


def test_an_empty_plan_never_builds_the_graph(monkeypatch, tmp_path) -> None:
    """The guard is taken before the framework is involved, not after an empty pass through it."""
    monkeypatch.setattr(workflow, "build_graph", refuse_to_build)
    assert run_audit(tmp_path, [])["remaining"] == []


def test_the_plan_the_caller_handed_in_is_left_untouched(tmp_path) -> None:
    """The loop consumes its own copy: the caller's list still reads as the plan it asked for."""
    plan = list(BOTH_STATIC_CHECKS)
    workflow.audit(str(tmp_path), [TOOL_SURFACE, DATA_SURFACE], MAPPING, plan)
    assert plan == BOTH_STATIC_CHECKS


def test_a_repository_that_does_not_exist_fails_loudly(tmp_path) -> None:
    """A check that cannot read the repository raises rather than reporting a clean app."""
    missing = tmp_path / "not-downloaded"
    with pytest.raises(FileNotFoundError, match=str(missing)):
        workflow.audit(str(missing), [], None, [TAINT_CHECK])


def test_a_check_name_the_workflow_does_not_know_is_refused(tmp_path) -> None:
    """A plan naming a check that does not exist must fail rather than run something else.

    The last branch of the dispatch is unguarded, so an unknown name falls
    through to the trace: its results are attributed to the unknown check and
    the name reaches `coverage.checks_run`, claiming a check ran that the
    auditor does not have.
    """
    with pytest.raises(ValueError, match="not_a_real_check"):
        workflow.audit(str(tmp_path), [], None, ["not_a_real_check"])
