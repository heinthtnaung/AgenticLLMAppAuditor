"""The four JavaScript/TypeScript detectors, each checked on an inline snippet."""

import pytest
from detector_helpers_js import FILE, only, other_detectors, run
from detectors_js import (
    find_agent_defs,
    find_data_sources,
    find_prompt_templates,
    find_tool_calls,
)
from languages import TYPESCRIPT
from surface import AGENT_DEF, DATA_SOURCE, PROMPT_TEMPLATE, TOOL_CALL

PROMPT_CALL = """
import { ChatPromptTemplate } from "@langchain/core/prompts";

const prompt = ChatPromptTemplate.fromMessages([["system", "be helpful"]]);
"""

PROMPT_MESSAGE = """
const messages = [{ role: "system", content: "You are a helpful assistant." }];
"""

AGENT_CALL = """
import { ChatOpenAI } from "@langchain/openai";

const model = new ChatOpenAI({ model: "gpt-4o" });
"""

TOOL_CALL_SOURCE = """
import { TavilySearchResults } from "@langchain/community/tools/tavily_search";

const tools = [new TavilySearchResults({ maxResults: 3 })];
"""

DATA_SOURCE_CALL = """
const page = await fetch("http://example.com/policy");
"""

RELATIVE_IMPORT = """
import { DynamicTool } from "./tools";

const lookup = new DynamicTool({ name: "lookup" });
"""

TYPE_ONLY_IMPORT = """
import type { AIMessage } from "@langchain/core/messages";

const count = 1;
"""


@pytest.mark.parametrize(
    "detector, source, kind",
    [
        (find_prompt_templates, PROMPT_CALL, PROMPT_TEMPLATE),
        (find_agent_defs, AGENT_CALL, AGENT_DEF),
        (find_tool_calls, TOOL_CALL_SOURCE, TOOL_CALL),
        (find_data_sources, DATA_SOURCE_CALL, DATA_SOURCE),
    ],
)
def test_detector_reports_its_own_kind(detector, source: str, kind: str) -> None:
    """Each detector finds the one surface its snippet contains, tagged with its own kind."""
    assert only(run(detector, source)).kind == kind


@pytest.mark.parametrize(
    "detector, source",
    [
        (find_prompt_templates, PROMPT_CALL),
        (find_agent_defs, AGENT_CALL),
        (find_tool_calls, TOOL_CALL_SOURCE),
        (find_data_sources, DATA_SOURCE_CALL),
    ],
)
def test_other_detectors_ignore_the_snippet(detector, source: str) -> None:
    """The other three detectors stay silent, so the four kinds never overlap."""
    for other in other_detectors(detector):
        assert run(other, source) == [], f"{other.__name__} also fired on this snippet"


def test_prompt_template_call_is_named_after_the_constructor() -> None:
    """A framework prompt builder is recorded under the call it makes."""
    assert only(run(find_prompt_templates, PROMPT_CALL)).name == "ChatPromptTemplate.fromMessages"


def test_inline_chat_message_is_a_prompt() -> None:
    """Prompt text written inline as {role, content} is a prompt surface."""
    assert only(run(find_prompt_templates, PROMPT_MESSAGE)).name == "system_message"


def test_surfaces_carry_the_typescript_language() -> None:
    """A surface from a .ts file records TypeScript, so its module is read as an npm package."""
    assert only(run(find_agent_defs, AGENT_CALL)).language == TYPESCRIPT


def test_surfaces_carry_the_given_file_label() -> None:
    """The detector records the caller's label rather than inventing a path."""
    assert only(run(find_tool_calls, TOOL_CALL_SOURCE)).file == FILE


def test_module_resolves_from_the_import() -> None:
    """A constructor's module is the package specifier it was imported from."""
    assert only(run(find_agent_defs, AGENT_CALL)).module == "@langchain/openai"


def test_tool_module_resolves_from_the_import() -> None:
    """Tool classes resolve their package the same way, so Phase 2 can map them to an SBOM."""
    surface = only(run(find_tool_calls, TOOL_CALL_SOURCE))
    assert surface.module == "@langchain/community/tools/tavily_search"


def test_relative_import_records_no_module() -> None:
    """First-party code is not an SBOM component, so a relative import records no module."""
    assert only(run(find_tool_calls, RELATIVE_IMPORT)).module == ""


def test_type_only_import_produces_no_surface() -> None:
    """`import type` disappears at build time, so it can never be a runtime surface."""
    for detector in (find_prompt_templates, find_agent_defs, find_tool_calls, find_data_sources):
        assert run(detector, TYPE_ONLY_IMPORT) == []


@pytest.mark.parametrize(
    "detector, source, line",
    [
        (find_prompt_templates, PROMPT_CALL, 3),
        (find_prompt_templates, PROMPT_MESSAGE, 1),
        (find_agent_defs, AGENT_CALL, 3),
        (find_tool_calls, TOOL_CALL_SOURCE, 3),
        (find_data_sources, DATA_SOURCE_CALL, 1),
    ],
)
def test_line_numbers_are_one_based(detector, source: str, line: int) -> None:
    """Lines are counted from 1, matching the Python backend and an editor's gutter."""
    assert only(run(detector, source)).line == line


SHELL_TOOL_SOURCE = """
import { ShellTool } from "langchain/tools";

const runner = new ShellTool();
"""

PROCESS_ENV_SOURCE = """
const key = process.env.OPENAI_API_KEY;
"""


def test_shell_tool_is_found_and_flagged_as_high_privilege() -> None:
    """A shell tool is the highest-severity LLM06 pattern and must never be missed."""
    surface = only(run(find_tool_calls, SHELL_TOOL_SOURCE))
    assert (surface.kind, surface.name) == (TOOL_CALL, "ShellTool")
    assert "shell, code, or network reach" in surface.detail


def test_process_env_is_found_as_a_data_source() -> None:
    """process.env is read as a property, not called, so it needs its own match."""
    surface = only(run(find_data_sources, PROCESS_ENV_SOURCE))
    assert (surface.kind, surface.name) == (DATA_SOURCE, "process.env.OPENAI_API_KEY")
