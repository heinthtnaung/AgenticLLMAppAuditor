"""The agentic audit workflow: a planner picking the next check over shared state.

Built on LangGraph because the thesis argues an agentic LLM app should be
audited by one, so the auditor is built the way the apps it audits are built. A
bounded loop does not need a framework, and that is not why it is here.

The loop is bounded by a step cap. An unbounded planner over someone else's
repository is exactly what the safety boundary exists to prevent, and the cap is
the mechanism rather than a promise.

The planner chooses *which check runs next*. It does not decide what counts as
a finding: that stays with the checks, which read evidence and cite it.
"""

import os
from typing import Annotated, TypedDict

# LangSmith would send traces off the machine -- node inputs and outputs, so
# the audited repository's paths, file names, surface names and line numbers.
# Assigned, never setdefault: a machine that develops LangChain apps commonly
# exports LANGSMITH_TRACING=true, and setdefault would yield to it. The auditor
# is offline, and that is not conditional on how the machine is configured.
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from langgraph.graph import END, START, StateGraph  # noqa: E402  (after the opt-out)

from artifacts.finding import Finding, Probe
from checks import (
    auditability, known_advisory, output_handling, permissions, supply_chain,
    taint)
from checks.plan_selection import surfaces_for

# One planner step runs one check, so this caps how many checks a single audit
# may run. Higher than the plan needs, so a new check does not silently stop
# the loop short; low enough that a planner bug cannot spin.
MAX_STEPS = 20

# Every check the planner knows how to run. A name outside this is refused.
KNOWN_CHECKS = (permissions.CHECK_NAME, supply_chain.CHECK_NAME, taint.CHECK_NAME,
                known_advisory.CHECK_NAME, output_handling.CHECK_NAME,
                auditability.CHECK_NAME)


def _extend(left: list, right: list) -> list:
    """Merge a node's results into the shared state, in the order they were found."""
    return left + right


class AuditState(TypedDict):
    """What every node reads and adds to. The plan is recorded, not just followed."""

    repo_path: str
    surfaces: list
    mapping_document: dict | None
    advisories: dict | None
    remaining: list[str]
    chosen: str | None
    selection: dict
    findings: Annotated[list[Finding], _extend]
    probes: Annotated[list[Probe], _extend]
    checks_run: Annotated[list[str], _extend]
    steps: int


def _mapping_for(name: str, state: AuditState) -> dict:
    """The surface-to-component mapping, refusing to run a check without one.

    Both component-anchored checks read it, and neither fails usefully on None.
    `supply_chain` raises `AttributeError: 'NoneType' object has no attribute
    'get'`, which names nothing a reader can act on. `known_advisory` is worse:
    it returns *no findings at all*, so `coverage.checks_run` names a check that
    ran over nothing and the artifact reads as "looked and found none" when the
    truth is "was handed nothing to look at".

    A check reaching here with no mapping is a dispatch bug -- `run_checks`
    decides eligibility from the same field -- so this refuses loudly rather
    than degrading. Degrading is for a missing generator, not for the auditor
    contradicting itself.
    """
    mapping = state["mapping_document"]
    if mapping is None:
        raise ValueError(
            f"{name} was dispatched but the mapping document is None; the check "
            "is only eligible when dependencies were readable, so this is a "
            "dispatch bug rather than a repository without a manifest")
    return mapping


def _advisories_for(name: str, state: AuditState) -> dict:
    """The advisory index, refusing to run the advisory check without one.

    The sibling of `_mapping_for`, and the same silence one argument over:
    `find_known_advisories` returns no findings for a null index exactly as it
    did for a null mapping, so `coverage.checks_run` named a check that was
    handed nothing. `run_checks._checks_that_examined_something` gates on both
    fields, so arriving here without either is the same dispatch bug.
    """
    advisories = state["advisories"]
    if advisories is None:
        raise ValueError(
            f"{name} was dispatched but no advisory index was ingested; the check "
            "is only eligible when Trivy produced one, so this is a dispatch bug "
            "rather than a run without advisory data")
    return advisories


def _run_one(name: str, state: AuditState,
             surfaces: list) -> tuple[list[Finding], list[Probe]]:
    """Run the named check over the surfaces the planner left it, and return what it concluded.

    `surfaces` rather than `state["surfaces"]`: the planner may narrow a check
    to some of them, and `plan_selection.surfaces_for` applies that once in
    `act` rather than in six branches. The two component-anchored checks below
    still read the whole list, because they are not narrowable -- filtering
    them would drop a component from both sides of the coverage ledger.
    """
    if name == permissions.CHECK_NAME:
        return permissions.find_over_privileged_tools(surfaces), []
    if name == supply_chain.CHECK_NAME:
        return supply_chain.find_undeclared_dependencies(
            _mapping_for(name, state),
            supply_chain.surface_fields(state["surfaces"])), []
    if name == taint.CHECK_NAME:
        return taint.run_over_repo(state["repo_path"], surfaces)
    if name == known_advisory.CHECK_NAME:
        return known_advisory.find_known_advisories(
            _mapping_for(name, state), _advisories_for(name, state),
            supply_chain.surface_fields(state["surfaces"])), []
    if name == output_handling.CHECK_NAME:
        return output_handling.run_over_repo(state["repo_path"], surfaces), []
    if name == auditability.CHECK_NAME:
        return auditability.run_over_repo(state["repo_path"], surfaces), []
    # Refused rather than fallen through: an unknown name would otherwise reach
    # coverage.checks_run claiming a check ran that this auditor does not have,
    # with another check's results attributed to it.
    raise ValueError(f"unknown check {name!r}; expected one of {KNOWN_CHECKS}")


def choose_next(remaining: list[str]) -> str:
    """Pick the check to run next: the first still outstanding.

    Deterministic, and the only place the pick is made. The *order* it walks is
    decided before the graph starts, so a model can inform that order without
    the graph ever calling one -- see `docs/HISTORY.md`.
    """
    if not remaining:
        raise ValueError("nothing left to choose from; should_continue ends the run first")
    return remaining[0]


def plan(state: AuditState) -> dict:
    """Pick the check that runs next, and record the decision as a step taken.

    The pick lives here rather than in `act` so that one node owns it: `act`
    used to take `remaining[0]` while `plan` only counted. That is a move, not
    a new decision -- today the pick is still the first outstanding check, and
    every eligible check runs whatever happens. From task 7.2 the *order* it
    walks is model-informed; which checks run is never the model's to choose.
    """
    return {"steps": state["steps"] + 1, "chosen": choose_next(state["remaining"])}


def act(state: AuditState) -> dict:
    """Run the check the planner chose and merge what it found into the state."""
    name = state["chosen"]
    if name is None:
        # Only reachable if `act` were wired to run before `plan`. Refused
        # rather than defaulted, because defaulting to `remaining[0]` would
        # silently restore the behaviour this split exists to remove.
        raise ValueError("act ran before plan chose a check")
    findings, probes = _run_one(
        name, state, surfaces_for(name, state["selection"], state["surfaces"]))
    left = list(state["remaining"])
    # The FIRST entry with that name, not every one. By name because the chooser
    # may pick from anywhere in the list, so dropping `remaining[0]` would drop
    # the wrong check; the first occurrence because a plan may legitimately name
    # one check twice, and filtering them all out collapses the loop to a single
    # step -- which silently removed the step cap's only end-to-end coverage.
    left.remove(name)
    return {
        "remaining": left,
        "findings": findings,
        "probes": probes,
        "checks_run": [name],
    }


def should_continue(state: AuditState) -> str:
    """Stop when nothing is left to run, or when the step cap is reached.

    The cap is not expected to bind: it is the backstop that keeps a planner
    bug from looping over someone else's repository.
    """
    if not state["remaining"] or state["steps"] >= MAX_STEPS:
        return END
    return "plan"


def build_graph() -> object:
    """Wire the planner and the check runner into a bounded loop."""
    graph = StateGraph(AuditState)
    graph.add_node("plan", plan)
    graph.add_node("act", act)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "act")
    graph.add_conditional_edges("act", should_continue, {"plan": "plan", END: END})
    return graph.compile()


def audit(repo_path: str, surfaces: list, mapping_document: dict | None,
          plan_order: list[str], advisories: dict | None = None,
          selection: dict | None = None) -> AuditState:
    """Run the planned checks over one app and return the state they built.

    `plan_order` is the planner's input, not a hardcoded sequence: only checks
    with something to examine on this app are handed to it, so `checks_run`
    reports what looked rather than what exists.
    """
    start: AuditState = {
        "repo_path": repo_path,
        "surfaces": surfaces,
        "mapping_document": mapping_document,
        "advisories": advisories,
        "remaining": list(plan_order),
        "chosen": None,
        "selection": dict(selection or {}),
        "findings": [],
        "probes": [],
        "checks_run": [],
        "steps": 0,
    }
    if not plan_order:
        return start
    return build_graph().invoke(start)
