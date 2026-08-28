"""The planner chooses which check runs; it never decides what counts as a finding.

That line is the plan's scope rule: a planner that judged evidence would be a
second detector sitting beside the checks, with its own opinion and no module
owning it. It is asserted two ways -- over the workflow's source, which names no
OWASP risk and builds no record of its own, and over its output, which is
exactly what the check returns when called directly.
"""

import ast
import re
from pathlib import Path

from artifacts.surface import TOOL_CALL, Surface
from checks import permissions, supply_chain, taint, workflow
from conftest import SRC_DIR
from parsing.languages import PYTHON

WORKFLOW_MODULE = Path("checks/workflow.py")

# An OWASP id as this project writes it: LLM01, LLM03, LLM06.
OWASP_ID_PATTERN = re.compile(r"LLM\d\d")

# The two records a check produces. The workflow may pass them around and name
# them in a type hint; building one would make it a detector.
RESULT_RECORDS = frozenset({"Finding", "Probe"})

# One surface the permission check reports on, so the comparison below is
# between two non-empty answers rather than two empty ones.
TOOL_SURFACE = Surface(TOOL_CALL, "ShellTool", "agent.py", 12, PYTHON, "tool", "langchain.tools")


def parse_module(relative: Path) -> ast.Module:
    """Parse one module under src/ into a syntax tree."""
    return ast.parse((SRC_DIR / relative).read_text(encoding="utf-8"))


def called_names(tree: ast.Module) -> set[str]:
    """Return the bare name of everything the module calls."""
    return {node.func.id for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}


def string_literals(tree: ast.Module) -> list[str]:
    """Return every string written in the module, docstrings included."""
    return [node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)]


def test_the_workflow_names_no_owasp_risk() -> None:
    """Mapping a problem to a risk is the checks' judgement, and it stays there."""
    written = " ".join(string_literals(parse_module(WORKFLOW_MODULE)))
    assert OWASP_ID_PATTERN.search(written) is None


def test_the_workflow_builds_no_finding_and_no_probe_of_its_own() -> None:
    """It merges what the checks concluded; it never adds a conclusion to the pile."""
    assert called_names(parse_module(WORKFLOW_MODULE)) & RESULT_RECORDS == set()


def test_the_checks_are_the_modules_that_do_name_a_risk() -> None:
    """Guard: the two tests above mean nothing unless someone owns the judgement."""
    assert {permissions.OWASP_ID, supply_chain.OWASP_ID, taint.OWASP_ID} == {
        "LLM06", "LLM03", "LLM01"}


def test_the_workflow_returns_exactly_what_the_check_concluded(tmp_path) -> None:
    """Planning a check does not edit, filter or add to its result."""
    surfaces = [TOOL_SURFACE]
    state = workflow.audit(str(tmp_path), surfaces, None, [permissions.CHECK_NAME])
    assert state["findings"] == permissions.find_over_privileged_tools(surfaces)
    assert state["findings"] != []
