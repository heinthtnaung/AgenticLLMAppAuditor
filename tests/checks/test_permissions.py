"""LLM06: a tool surface whose class grants a shell, an interpreter or the network.

The rule is a named list, not an inference, so the tests are about which
surfaces reach it: the class must be listed *and* the surface must be a tool
call. It is also run over extracted surfaces at both ends -- a written app
whose tools are ordinary, and one that really does instantiate a shell -- so
"reports nothing" is shown to be a decision rather than a check that never
fires.

Those two apps are written by the tests. The pinned ones this used to run over
are gone, so no tool name here was chosen by anyone but this project's authors.
"""

import pytest

from artifacts.finding import STATIC
from artifacts.surface import AGENT_DEF, DATA_SOURCE, TOOL_CALL, Surface
from checks.permissions import CHECK_NAME, OWASP_ID, find_over_privileged_tools
from detectors.detector_names import HIGH_PRIVILEGE_TOOLS
from mixed_app_fixtures import PYTHON_FILE, write_mixed_app
from parsing.extractor import extract_repo
from parsing.languages import PYTHON

APP_FILE = "app/agent.py"

# A tool class carrying no shell, interpreter or network capability.
ORDINARY_TOOL = "GetUserTransactions"

# A written app whose one tool carries no privileged capability, so a check
# that fired on everything would be caught here rather than assumed harmless.
ORDINARY_APP_FILE = "ordinary.py"
ORDINARY_APP_SOURCE = f'''from langchain.tools import Tool

lookup = Tool(name="{ORDINARY_TOOL}", func=None)
'''


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


def test_an_app_of_ordinary_tools_yields_no_finding(tmp_path) -> None:
    """Run over extracted surfaces, not written ones: the check invents nothing."""
    (tmp_path / ORDINARY_APP_FILE).write_text(ORDINARY_APP_SOURCE, encoding="utf-8")
    surfaces = extract_repo(str(tmp_path)).surfaces
    assert surfaces, "the app yielded no surfaces, so a clean result proves nothing"
    assert find_over_privileged_tools(surfaces) == []


def test_an_app_that_really_instantiates_a_shell_is_reported(tmp_path) -> None:
    """The other end of the same path: extraction to finding, over a written app."""
    surfaces = extract_repo(str(write_mixed_app(tmp_path))).surfaces
    findings = find_over_privileged_tools(surfaces)
    assert [(f.file, f.surface_name) for f in findings] == [(PYTHON_FILE, "ShellTool")]
