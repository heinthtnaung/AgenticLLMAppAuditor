"""The step cap bounds the loop: the safety mechanism, asserted rather than promised.

An unbounded planner over a third-party repository is what the project's safety
boundary exists to prevent, so it is not enough that the cap exists and that a
three-check plan finishes well inside it. The tests below hand the loop more
work than the cap allows and assert it stops early with that work still
outstanding -- and that the checks it never reached are absent from the record,
so a truncated run can never be read as a complete one.

The cap staying slack is load-bearing elsewhere, which is why this file also
pins it against `KNOWN_CHECKS`. Four documents argue that the planner's order
cannot change `findings.json` *because* "MAX_STEPS cannot bind on six checks".
If the auditor ever grows past the cap, that reasoning fails and the order --
the one model-chosen value in the run -- would start deciding which checks
never run at all.
"""

from pathlib import Path

import pytest

from checks import workflow
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.run_checks import CHECK_NAMES, EDGE_CHECKS, GRAPH_CHECKS
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_CHECK
from checks.workflow import KNOWN_CHECKS, MAX_STEPS, choose_next, should_continue
from langgraph.graph import END

# More checks than any cap under test allows, so the loop must stop short.
OVERLONG_PLAN = [PERMISSION_CHECK] * (MAX_STEPS + 5)

# A cap low enough to bite within a plan a reader can count.
LOW_CAP = 2

# The checks the runner knows how to dispatch, counted by hand so an emptied
# `KNOWN_CHECKS` cannot make the slack assertion below pass over nothing.
KNOWN_CHECK_COUNT = 6


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


def test_the_planner_knows_exactly_the_checks_the_runner_can_run() -> None:
    """Both lists are written by hand, and a name in one and not the other breaks an audit.

    `run_checks.GRAPH_CHECKS` is every check that declares a risk class and runs
    inside the loop; `workflow.KNOWN_CHECKS` is what `_run_one` knows how to
    dispatch. A name planned but unknown raises part-way through someone else's
    audit, and a name known but never planned is a check that silently stopped
    running. So this is a plain equality, and the subtraction that used to stand
    in its place now lives in `run_checks` where a reader of the source meets
    it -- an invariant written inside an assertion can be weakened by editing
    the assertion.
    """
    assert set(KNOWN_CHECKS) == set(GRAPH_CHECKS), (
        f"planned but not runnable: {sorted(set(GRAPH_CHECKS) - set(KNOWN_CHECKS))}; "
        f"runnable but never planned: {sorted(set(KNOWN_CHECKS) - set(CHECK_NAMES))}; "
        f"dispatched from a graph node despite needing the model: "
        f"{sorted(set(KNOWN_CHECKS) & set(EDGE_CHECKS))}")


def test_the_graph_checks_are_every_declared_check_but_the_edge_ones() -> None:
    """What the equality above rests on: the split is exhaustive and the halves are disjoint.

    An edge check runs in `build_findings`, outside the graph, because it needs
    the model and `tests/parsing/test_offline.py` asserts the graph attempts no
    socket. It still declares its risk class, so it is in `CHECK_NAMES`; putting
    it in `KNOWN_CHECKS` would let the planner dispatch it from a node, which is
    the thing the split prevents. A misspelled edge name would leave the derived
    tuple naming a check the graph cannot run, and re-hide the drift above.
    """
    assert EDGE_CHECKS
    assert set(EDGE_CHECKS) <= set(CHECK_NAMES)
    assert set(GRAPH_CHECKS) | set(EDGE_CHECKS) == set(CHECK_NAMES)
    assert set(GRAPH_CHECKS) & set(EDGE_CHECKS) == set()


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


def test_the_cap_cannot_bind_on_the_checks_the_auditor_knows_how_to_run() -> None:
    """`MAX_STEPS` must stay slack, or the planner's order starts subtracting checks.

    `docs/SCHEMAS.md`, `docs/FLOW.md`, `docs/PHASE_7_PLAN.md` and
    `src/artifacts/planner_document.py` all argue that the model-chosen order
    provably changes nothing in `findings.json`, and every one of them rests on
    the cap not binding. Add a check past the cap and the argument inverts: the
    order would decide which checks are reached, the ones left over would be
    absent from `coverage.checks_run`, and `src/evaluation/scorer.py` reads that
    absence as `no_check_for_risk_class` -- a recall loss wearing coverage
    vocabulary, which is the one thing Phase 7 forbids the planner to cause.

    Raise `MAX_STEPS` above the number of checks; do not delete this test.
    """
    assert len(KNOWN_CHECKS) < MAX_STEPS, (
        f"{len(KNOWN_CHECKS)} checks against a cap of {MAX_STEPS}: the planner's "
        "order would decide which checks never run, and their absence would reach "
        "coverage.checks_run, which the scorer reads as no_check_for_risk_class")


def test_the_known_checks_are_the_six_this_file_counts() -> None:
    """Guard: an emptied tuple would make the cap test above pass over nothing."""
    assert len(KNOWN_CHECKS) == KNOWN_CHECK_COUNT


def test_choosing_from_an_empty_plan_is_refused_with_a_clear_error() -> None:
    """A bare `IndexError` says nothing; this says which invariant broke and where.

    `should_continue` ends the run before `remaining` empties, so reaching
    `choose_next([])` means that guard failed -- rule 8 says the error has to
    tell the reader that, not just that a list was short.
    """
    with pytest.raises(ValueError, match="nothing left to choose from"):
        choose_next([])


def test_choosing_from_a_plan_takes_the_first_check_still_outstanding() -> None:
    """Guard: without this the refusal above would pass on a `choose_next` that never chooses."""
    assert choose_next([SUPPLY_CHAIN_CHECK, PERMISSION_CHECK]) == SUPPLY_CHAIN_CHECK
