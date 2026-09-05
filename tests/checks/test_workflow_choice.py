"""The planner makes the choice: `plan` picks the check and `act` runs the one it picked.

A sibling of test_workflow.py, which is at the ~200-line cap, and split on the
same lines its two other siblings are: the step cap is in test_workflow_cap.py,
the planner/detector boundary in test_workflow_scope.py, and the choice itself
here.

Worth its own file because the split moved one expression and changed nothing an
end-to-end audit reports -- `checks_run` is identical before and after. The three
ways it can regress are all invisible to a full run over a plan whose chosen
check is already `remaining[0]`: `act` falling back to `remaining[0]` when
nothing was chosen, `act` dropping `remaining[0]` by position instead of the
check it ran by name, and `plan` counting a step without recording a choice.
Each is asserted below over `plan` and `act` called directly, with a `chosen`
that is deliberately *not* the head of `remaining`.
"""

from pathlib import Path

import pytest

from artifacts.surface import DATA_SOURCE, TOOL_CALL, Surface
from checks import workflow
from checks.output_handling import CHECK_NAME as QUERY_CHECK
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK
from parsing.languages import PYTHON

# A privileged tool, so the permission check has exactly one finding to report:
# the evidence that the check named in `chosen` is the one that actually ran.
TOOL_SURFACE = Surface(TOOL_CALL, "ShellTool", "agent.py", 12, PYTHON, "tool", "langchain.tools")

# A surface no check below reports on, present so the state is not degenerate.
DATA_SURFACE = Surface(DATA_SOURCE, "yaml.load", "utils.py", 75, PYTHON, "yaml read", "yaml")

# A mapping that joined nothing: the supply-chain check reads it and reports
# nothing, which is what makes it usable as a second name in the plans below.
EMPTY_MAPPING = {"entries": []}

# Three outstanding checks whose head is neither of the two chosen below, so a
# chooser or a remover that used position would pick or drop the wrong one.
THREE_OUTSTANDING = [QUERY_CHECK, PERMISSION_CHECK, SUPPLY_CHAIN_CHECK]


def state_for(repo: Path, chosen: str | None, remaining: list[str]) -> dict:
    """The parts of the audit state `plan` and `act` read, with nothing run yet."""
    return {
        "repo_path": str(repo),
        "surfaces": [TOOL_SURFACE, DATA_SURFACE],
        "mapping_document": EMPTY_MAPPING,
        "advisories": None,
        "remaining": list(remaining),
        "chosen": chosen,
        # Empty: no check is narrowed here, so every one of them examines both
        # surfaces. What a non-empty selection does is test_workflow_selection.py.
        "selection": {},
        "findings": [],
        "probes": [],
        "checks_run": [],
        "steps": 0,
    }


def test_choose_next_picks_the_first_outstanding_check() -> None:
    """The one place the decision is made, and it is deterministic."""
    assert workflow.choose_next(THREE_OUTSTANDING) == QUERY_CHECK


def test_plan_records_the_check_it_chose(tmp_path) -> None:
    """`plan` returns the choice, not only a step count: that is what 7.0 moved."""
    assert workflow.plan(state_for(tmp_path, None, THREE_OUTSTANDING)) == {
        "steps": 1, "chosen": QUERY_CHECK}


def test_act_refuses_to_run_when_the_planner_chose_nothing(tmp_path) -> None:
    """No silent fallback to `remaining[0]`: that would restore what the split removed.

    `remaining` here holds a check that would succeed and return a finding, so
    a fallback would return normally and this `raises` would fail.
    """
    with pytest.raises(ValueError, match="act ran before plan chose a check"):
        workflow.act(state_for(tmp_path, None, [PERMISSION_CHECK]))


def test_act_runs_the_chosen_check_rather_than_the_head_of_remaining(tmp_path) -> None:
    """The chosen check is second in the plan, so running the head would show as a wrong name."""
    result = workflow.act(state_for(tmp_path, PERMISSION_CHECK, THREE_OUTSTANDING))
    assert result["checks_run"] == [PERMISSION_CHECK]
    assert [finding.rule_id for finding in result["findings"]] == [PERMISSION_CHECK]


def test_act_removes_the_check_it_ran_by_name_not_by_position(tmp_path) -> None:
    """The chosen name goes and the other two survive, in the order they were planned."""
    result = workflow.act(state_for(tmp_path, PERMISSION_CHECK, THREE_OUTSTANDING))
    assert result["remaining"] == [QUERY_CHECK, SUPPLY_CHAIN_CHECK]


def test_act_removes_the_last_planned_check_when_that_is_the_one_chosen(tmp_path) -> None:
    """Guard: the tail is the position a by-position remover would never reach."""
    result = workflow.act(state_for(tmp_path, SUPPLY_CHAIN_CHECK, THREE_OUTSTANDING))
    assert result["checks_run"] == [SUPPLY_CHAIN_CHECK]
    assert result["remaining"] == [QUERY_CHECK, PERMISSION_CHECK]


def test_the_state_the_planner_carries_the_choice_in_is_declared(tmp_path) -> None:
    """`chosen` is part of the state contract, so a node may read it and LangGraph may set it."""
    assert "chosen" in workflow.AuditState.__annotations__
    assert workflow.audit(str(tmp_path), [], EMPTY_MAPPING, [])["chosen"] is None


def test_every_planned_check_runs_exactly_once_in_the_order_planned(tmp_path) -> None:
    """End to end over four checks: `checks_run` is the plan, unchanged by the split.

    The pre-7.0 loop walked `remaining` from the front, so this is the record it
    produced; asserting equality with the plan is what pins the behaviour as
    unchanged. Every check is dispatched over an empty repository with no
    mapping, where each is silent and cheap.
    """
    plan_order = [TAINT_CHECK, PERMISSION_CHECK, QUERY_CHECK, SUPPLY_CHAIN_CHECK]
    state = workflow.audit(str(tmp_path), [TOOL_SURFACE], EMPTY_MAPPING, plan_order)
    assert state["checks_run"] == plan_order
    assert state["remaining"] == []
    assert state["steps"] == len(plan_order)
