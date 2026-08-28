"""The step cap bounds the loop: the safety mechanism, asserted rather than promised.

An unbounded planner over a third-party repository is what the project's safety
boundary exists to prevent, so it is not enough that the cap exists and that a
three-check plan finishes well inside it. The tests below hand the loop more
work than the cap allows and assert it stops early with that work still
outstanding -- and that the checks it never reached are absent from the record,
so a truncated run can never be read as a complete one.
"""

from pathlib import Path

from checks import workflow
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.run_checks import CHECK_NAMES
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_CHECK
from checks.workflow import MAX_STEPS, should_continue
from langgraph.graph import END

# More checks than any cap under test allows, so the loop must stop short.
OVERLONG_PLAN = [PERMISSION_CHECK] * (MAX_STEPS + 5)

# A cap low enough to bite within a plan a reader can count.
LOW_CAP = 2


def run_plan(repo: Path, plan_order: list[str]) -> dict:
    """Run the workflow over an empty repository, where every check is cheap and silent."""
    return workflow.audit(str(repo), [], None, list(plan_order))


def state_at(steps: int, remaining: list[str]) -> dict:
    """Build the part of the state the stop condition reads."""
    return {"steps": steps, "remaining": remaining}


def test_the_loop_stops_at_the_cap_with_work_still_outstanding(monkeypatch, tmp_path) -> None:
    """Two of five checks run, and the other three are still listed as unrun."""
    monkeypatch.setattr(workflow, "MAX_STEPS", LOW_CAP)
    state = run_plan(tmp_path, [PERMISSION_CHECK] * 5)
    assert state["steps"] == LOW_CAP
    assert len(state["checks_run"]) == LOW_CAP
    assert len(state["remaining"]) == 5 - LOW_CAP


def test_a_capped_run_never_records_a_check_it_did_not_reach(monkeypatch, tmp_path) -> None:
    """The truncated check is absent, so no coverage built from this can claim it looked."""
    monkeypatch.setattr(workflow, "MAX_STEPS", 1)
    state = run_plan(tmp_path, [PERMISSION_CHECK, SUPPLY_CHAIN_CHECK])
    assert state["checks_run"] == [PERMISSION_CHECK]
    assert state["remaining"] == [SUPPLY_CHAIN_CHECK]


def test_the_real_cap_bounds_a_plan_longer_than_itself(tmp_path) -> None:
    """MAX_STEPS itself binds, not just a patched one, and the framework does not stop first."""
    state = run_plan(tmp_path, OVERLONG_PLAN)
    assert state["steps"] == MAX_STEPS
    assert len(state["checks_run"]) == MAX_STEPS
    assert len(state["remaining"]) == len(OVERLONG_PLAN) - MAX_STEPS


def test_the_cap_is_higher_than_the_checks_the_auditor_actually_has() -> None:
    """A real plan is never truncated, so the cap is a backstop rather than a limit in use."""
    assert MAX_STEPS > len(CHECK_NAMES)


def test_the_loop_stops_when_nothing_is_left_to_run() -> None:
    """The ordinary exit: the plan is exhausted well before the cap."""
    assert should_continue(state_at(steps=1, remaining=[])) == END


def test_the_loop_stops_at_the_cap_even_with_checks_left() -> None:
    """The cap wins over outstanding work, which is the whole point of having one."""
    assert should_continue(state_at(steps=MAX_STEPS, remaining=[PERMISSION_CHECK])) == END


def test_the_loop_continues_while_it_is_under_the_cap_with_work_left() -> None:
    """Guard: without this the two stop tests would pass on a loop that never runs."""
    assert should_continue(state_at(steps=1, remaining=[PERMISSION_CHECK])) == "plan"


def test_the_step_just_past_the_cap_stops_too() -> None:
    """The comparison is `>=`, so an off-by-one in the counter cannot slip past it."""
    assert should_continue(state_at(steps=MAX_STEPS + 1, remaining=[PERMISSION_CHECK])) == END
