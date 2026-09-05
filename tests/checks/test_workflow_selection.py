"""The narrowing reaching the graph: `act` filters once, and two checks are never filtered.

A sibling of test_workflow_choice.py, which owns the pick. This one owns what
the pick is handed. `workflow.audit` takes a `selection`, `act` applies
`plan_selection.surfaces_for` once, and `_run_one` receives the filtered list --
so a check that was narrowed really does see fewer surfaces rather than merely
being recorded as having seen fewer. That gap is the one worth testing: the
record and the run are written in different modules, and a narrowing that is
published but not applied is a false statement in `findings.json`.

The two component-anchored checks are the exception, and it is asserted here as
well as in `plan_selection`: `_run_one` hands them `state["surfaces"]` whatever
the selection says. Belt and braces on purpose -- if rule 4 were ever removed
from the guard, this is what would still stop a component vanishing from both
sides of the coverage ledger.

Two privileged tools, so "narrowed to one" and "examined both" are one finding
apart. Nothing here reaches a model or a server: the checks that run are static.
"""

from pathlib import Path

from artifacts.mapping import MAPPING_REASONS, USED_BUT_UNDECLARED
from artifacts.surface import DATA_SOURCE, TOOL_CALL, Surface
from checks import workflow
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_CHECK
from parsing.languages import PYTHON

# Two privileged tools and one data source. The permission check reports both
# tools, so a narrowing to one is visible as a finding count of one.
SHELL = Surface(TOOL_CALL, "ShellTool", "agent.py", 12, PYTHON, "tool", "langchain.tools")
REPL = Surface(TOOL_CALL, "PythonREPLTool", "agent.py", 20, PYTHON, "tool", "langchain.tools")
DATA = Surface(DATA_SOURCE, "yaml.load", "utils.py", 75, PYTHON, "yaml read", "yaml")
SURFACES = [SHELL, REPL, DATA]

BOTH_TOOLS = 2

# A mapping the supply-chain check reports one undeclared component from. Its
# entry is anchored on the data surface, which every narrowing below excludes.
MAPPING = {
    "entries": [{"surface_id": DATA.id, "reason": USED_BUT_UNDECLARED,
                 "component_name": "pyyaml"}],
    "reason_counts": {reason: 0 for reason in MAPPING_REASONS} | {USED_BUT_UNDECLARED: 1},
}


def run(repo: Path, plan_order: list[str], selection: dict | None = None) -> dict:
    """Audit the fixture surfaces with one plan and one narrowing."""
    return workflow.audit(str(repo), SURFACES, MAPPING, plan_order, None, selection)


def rule_ids(state: dict) -> list[str]:
    """The rule each finding was reported under, in the order the state holds them."""
    return [finding.rule_id for finding in state["findings"]]


# --- the selection is part of the state contract ----------------------------

def test_the_state_declares_the_selection_the_planner_carries(tmp_path) -> None:
    """A node may read it and LangGraph may carry it, so it has to be declared."""
    assert "selection" in workflow.AuditState.__annotations__


def test_an_audit_given_no_selection_starts_with_an_empty_one(tmp_path) -> None:
    """No planner, no narrowing: `{}` rather than `None`, so `act` never branches on absence."""
    assert run(tmp_path, [])["selection"] == {}


def test_the_selection_is_copied_rather_than_aliased(tmp_path) -> None:
    """The caller's dict must not be editable through the state the graph carries."""
    selection = {PERMISSION_CHECK: {SHELL.id}}
    state = run(tmp_path, [PERMISSION_CHECK], selection)
    state["selection"][PERMISSION_CHECK] = set()
    assert selection == {PERMISSION_CHECK: {SHELL.id}}


# --- a narrowed check really sees fewer surfaces ----------------------------

def test_an_unnarrowed_check_reports_both_privileged_tools(tmp_path) -> None:
    """The baseline the narrowing is measured against, asserted rather than assumed."""
    state = run(tmp_path, [PERMISSION_CHECK])
    assert len(state["findings"]) == BOTH_TOOLS


def test_a_check_narrowed_to_one_tool_reports_only_that_tool(tmp_path) -> None:
    """The narrowing is applied, not merely recorded: one surface in, one finding out."""
    state = run(tmp_path, [PERMISSION_CHECK], {PERMISSION_CHECK: {SHELL.id}})
    assert [finding.surface_name for finding in state["findings"]] == ["ShellTool"]


def test_a_narrowed_check_is_still_named_in_checks_run(tmp_path) -> None:
    """It looked, so it is present. Absent, `docs/SCHEMAS.md` would read it as unable to look."""
    state = run(tmp_path, [PERMISSION_CHECK], {PERMISSION_CHECK: {SHELL.id}})
    assert state["checks_run"] == [PERMISSION_CHECK]


def test_a_selection_naming_no_surface_this_app_has_reports_nothing(tmp_path) -> None:
    """The state `plan_selection` refuses upstream, so the graph must not crash on it."""
    state = run(tmp_path, [PERMISSION_CHECK], {PERMISSION_CHECK: {"nowhere.py:1:TOOL_CALL:Ghost"}})
    assert state["findings"] == []
    assert state["checks_run"] == [PERMISSION_CHECK]


def test_narrowing_one_check_does_not_narrow_the_other(tmp_path) -> None:
    """Two checks in one plan: only the one named in the selection is filtered."""
    state = run(tmp_path, [PERMISSION_CHECK, SUPPLY_CHAIN_CHECK],
                {PERMISSION_CHECK: {SHELL.id}})
    assert rule_ids(state) == [PERMISSION_CHECK, SUPPLY_CHAIN_CHECK]


# --- rule 4: the component-anchored checks read the whole list --------------

def test_the_supply_chain_check_reads_every_surface_whatever_the_selection_says(
        tmp_path) -> None:
    """Its mapping entry is anchored on a surface this selection excludes, and it reports anyway.

    Filtering it would make `pyyaml` vanish from both sides of the ledger at
    once -- no finding about it, and no count of it as unreached. The guard
    refuses to narrow it; `_run_one` is the second lock on the same door.
    """
    state = run(tmp_path, [SUPPLY_CHAIN_CHECK], {SUPPLY_CHAIN_CHECK: {SHELL.id}})
    assert rule_ids(state) == [SUPPLY_CHAIN_CHECK]


def test_the_supply_chain_check_reports_the_same_thing_narrowed_or_not(tmp_path) -> None:
    """Stated as an equality, so a partial filter would show up as well as a total one."""
    narrowed = run(tmp_path / "a", [SUPPLY_CHAIN_CHECK], {SUPPLY_CHAIN_CHECK: {SHELL.id}})
    whole = run(tmp_path / "b", [SUPPLY_CHAIN_CHECK])
    assert narrowed["findings"] == whole["findings"]
