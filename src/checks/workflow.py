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
from checks import permissions, supply_chain, taint

# One planner step runs one check, so this caps how many checks a single audit
# may run. Higher than the plan needs, so a new check does not silently stop
# the loop short; low enough that a planner bug cannot spin.
MAX_STEPS = 20

# Every check the planner knows how to run. A name outside this is refused.
KNOWN_CHECKS = (permissions.CHECK_NAME, supply_chain.CHECK_NAME, taint.CHECK_NAME)


def _extend(left: list, right: list) -> list:
    """Merge a node's results into the shared state, in the order they were found."""
    return left + right


class AuditState(TypedDict):
    """What every node reads and adds to. The plan is recorded, not just followed."""

    repo_path: str
    surfaces: list
    mapping_document: dict | None
    remaining: list[str]
    findings: Annotated[list[Finding], _extend]
    probes: Annotated[list[Probe], _extend]
    checks_run: Annotated[list[str], _extend]
    steps: int


def _run_one(name: str, state: AuditState) -> tuple[list[Finding], list[Probe]]:
    """Run the named check and return what it concluded."""
    if name == permissions.CHECK_NAME:
        return permissions.find_over_privileged_tools(state["surfaces"]), []
    if name == supply_chain.CHECK_NAME:
        return supply_chain.find_undeclared_dependencies(
            state["mapping_document"], supply_chain.surface_fields(state["surfaces"])), []
    if name == taint.CHECK_NAME:
        return taint.run_over_repo(state["repo_path"], state["surfaces"])
    # Refused rather than fallen through: an unknown name would otherwise reach
    # coverage.checks_run claiming a check ran that this auditor does not have,
    # with another check's results attributed to it.
    raise ValueError(f"unknown check {name!r}; expected one of {KNOWN_CHECKS}")


def plan(state: AuditState) -> dict:
    """Decide which check runs next, and record the decision as a step taken."""
    return {"steps": state["steps"] + 1}


def act(state: AuditState) -> dict:
    """Run the check the planner chose and merge what it found into the state."""
    name = state["remaining"][0]
    findings, probes = _run_one(name, state)
    return {
        "remaining": state["remaining"][1:],
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
          plan_order: list[str]) -> AuditState:
    """Run the planned checks over one app and return the state they built.

    `plan_order` is the planner's input, not a hardcoded sequence: only checks
    with something to examine on this app are handed to it, so `checks_run`
    reports what looked rather than what exists.
    """
    start: AuditState = {
        "repo_path": repo_path,
        "surfaces": surfaces,
        "mapping_document": mapping_document,
        "remaining": list(plan_order),
        "findings": [],
        "probes": [],
        "checks_run": [],
        "steps": 0,
    }
    if not plan_order:
        return start
    return build_graph().invoke(start)
