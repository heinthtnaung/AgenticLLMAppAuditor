"""LLM06: a tool surface whose class grants a shell, an interpreter or the network.

The rule is a named list, not an inference, so the tests are about which
surfaces reach it: the class must be listed *and* the surface must be a tool
call. Both corpus fixtures are checked too, because a check that fires on
neither of them must be shown to fire on nothing rather than assumed to.
"""

import pytest

from artifacts.finding import STATIC
from artifacts.surface import AGENT_DEF, DATA_SOURCE, TOOL_CALL, Surface
from checks.permissions import CHECK_NAME, OWASP_ID, find_over_privileged_tools
from dependency_fixtures import corpus_surfaces, js_surfaces
from detectors.detector_names import HIGH_PRIVILEGE_TOOLS
from parsing.languages import PYTHON

APP_FILE = "app/agent.py"

# A tool class carrying no shell, interpreter or network capability.
ORDINARY_TOOL = "GetUserTransactions"


def tool_surface(name: str, kind: str = TOOL_CALL, line: int = 12) -> Surface:
    """Build one surface for the check to run over."""
    return Surface(kind, name, APP_FILE, line, PYTHON, "tool instantiated", "langchain.tools")


def test_a_shell_tool_is_reported_as_over_privileged() -> None:
    """The straightforward case: a shell tool is excessive agency."""
    findings = find_over_privileged_tools([tool_surface("ShellTool")])
    assert len(findings) == 1
    assert (findings[0].owasp_id, findings[0].rule_id) == (OWASP_ID, CHECK_NAME)


def test_the_finding_cites_the_surface_that_produced_it() -> None:
    """Every finding carries the surface id and its copied location."""
    finding = find_over_privileged_tools([tool_surface("ShellTool")])[0]
    assert finding.surface_id == f"{APP_FILE}:12:{TOOL_CALL}:ShellTool"
    assert (finding.surface_kind, finding.surface_name) == (TOOL_CALL, "ShellTool")
    assert (finding.file, finding.line) == (APP_FILE, 12)


def test_the_finding_is_static_and_names_no_probe() -> None:
    """Nothing was executed to reach it, and the record says so."""
    finding = find_over_privileged_tools([tool_surface("ShellTool")])[0]
    assert finding.detection == STATIC
    assert finding.probe_id is None


@pytest.mark.parametrize("name", sorted(HIGH_PRIVILEGE_TOOLS))
def test_every_listed_privileged_class_is_reported(name: str) -> None:
    """The rule is the list, so each name on it must actually reach a finding."""
    assert len(find_over_privileged_tools([tool_surface(name)])) == 1


def test_an_ordinary_tool_is_not_reported() -> None:
    """A tool with no privileged capability is not this check's finding."""
    assert find_over_privileged_tools([tool_surface(ORDINARY_TOOL)]) == []


@pytest.mark.parametrize("kind", (AGENT_DEF, DATA_SOURCE))
def test_a_privileged_name_on_another_surface_kind_is_not_reported(kind: str) -> None:
    """The check is about tools the agent may call, not about every mention of the name."""
    assert find_over_privileged_tools([tool_surface("ShellTool", kind=kind)]) == []


def test_no_surfaces_produces_no_findings() -> None:
    """An app with nothing to check is a clean result, not an error."""
    assert find_over_privileged_tools([]) == []


def test_each_privileged_surface_gets_its_own_finding() -> None:
    """Two shells in one file are two findings, distinguished by their surface ids."""
    findings = find_over_privileged_tools(
        [tool_surface("ShellTool"), tool_surface("PythonREPLTool", line=20)])
    assert len({finding.id for finding in findings}) == 2


def test_the_python_corpus_app_uses_no_privileged_tool_class() -> None:
    """Its graded LLM06 is a missing authorisation check, which this rule cannot see."""
    assert find_over_privileged_tools(corpus_surfaces()) == []


def test_the_javascript_corpus_app_uses_no_privileged_tool_class() -> None:
    """The clean fixture stays clean: this check invents nothing on it."""
    assert find_over_privileged_tools(js_surfaces()) == []
