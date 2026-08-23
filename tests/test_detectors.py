"""Each detector finds its own surface kind on small snippets and ignores the others."""

import ast
import textwrap

import pytest
from detectors import find_agent_defs, find_data_sources, find_prompt_templates, find_tool_calls
from surface import AGENT_DEF, DATA_SOURCE, PROMPT_TEMPLATE, TOOL_CALL

FILE = "app/snippet.py"

PROMPT_CALL_SOURCE = """
from langchain.prompts import ChatPromptTemplate

chat_prompt = ChatPromptTemplate.from_messages([("system", "be helpful")])
"""

PROMPT_STRING_SOURCE = """
import os

system_prompt = "You are a helpful support assistant."
"""

AGENT_SOURCE = """
from langchain.agents import create_react_agent

agent = create_react_agent(llm, tools)
"""

TOOL_DECORATOR_SOURCE = """
from langchain_core.tools import tool


@tool
def lookup_user(user_id):
    return user_id
"""

TOOL_CONSTRUCTOR_SOURCE = """
from langchain.agents import Tool

lookup = Tool(name="GetUserTransactions", func=None, description="reads rows")
"""

TOOL_SUBCLASS_SOURCE = """
from langchain_core.tools import BaseTool


class ShellRunner(BaseTool):
    name = "shell"
"""

DATA_SOURCE_SOURCE = """
import requests

page = requests.get("http://example.com")
"""

ROUTE_SOURCE = """
@app.post("/chat")
def chat(message):
    return message
"""

ALL_DETECTORS = (find_prompt_templates, find_agent_defs, find_tool_calls, find_data_sources)


def parse(source: str) -> ast.AST:
    """Parse a snippet, keeping its line numbers as written after the leading newline."""
    return ast.parse(textwrap.dedent(source).lstrip("\n"))


def only(surfaces: list) -> object:
    """Return the single surface a detector found, failing if it found anything else."""
    assert len(surfaces) == 1, f"expected exactly one surface, got {[s.name for s in surfaces]}"
    return surfaces[0]


def other_detectors(detector) -> list:
    """Return the three detectors that should stay silent on another one's construct."""
    return [candidate for candidate in ALL_DETECTORS if candidate is not detector]


# --- Prompt templates ------------------------------------------------------
def test_finds_prompt_template_constructor() -> None:
    """A framework prompt class is reported as a PROMPT_TEMPLATE at its own line."""
    surface = only(find_prompt_templates(parse(PROMPT_CALL_SOURCE), FILE))
    assert (surface.kind, surface.name, surface.line) == (
        PROMPT_TEMPLATE,
        "ChatPromptTemplate.from_messages",
        3,
    )


def test_prompt_template_module_comes_from_the_import() -> None:
    """The prompt surface records the module the prompt class was imported from."""
    surface = only(find_prompt_templates(parse(PROMPT_CALL_SOURCE), FILE))
    assert surface.module == "langchain.prompts"


def test_finds_prompt_shaped_string_assignment() -> None:
    """A string assigned to a prompt-shaped name is reported at its real line."""
    surface = only(find_prompt_templates(parse(PROMPT_STRING_SOURCE), FILE))
    assert (surface.kind, surface.name, surface.line) == (PROMPT_TEMPLATE, "system_prompt", 3)


def test_ignores_plain_string_assignment() -> None:
    """A string with no prompt-shaped name is not a prompt surface."""
    assert find_prompt_templates(parse("greeting = \"hello\"\n"), FILE) == []


# --- Agent definitions -----------------------------------------------------
def test_finds_agent_factory_call() -> None:
    """An agent factory call is reported as an AGENT_DEF at its own line."""
    surface = only(find_agent_defs(parse(AGENT_SOURCE), FILE))
    assert (surface.kind, surface.name, surface.line) == (AGENT_DEF, "create_react_agent", 3)


def test_agent_module_comes_from_the_import() -> None:
    """The agent surface records the module the factory was imported from."""
    surface = only(find_agent_defs(parse(AGENT_SOURCE), FILE))
    assert surface.module == "langchain.agents"


# --- Tool definitions ------------------------------------------------------
def test_finds_tool_decorated_function() -> None:
    """A @tool function is reported as a TOOL_CALL at the def line, not the decorator."""
    surface = only(find_tool_calls(parse(TOOL_DECORATOR_SOURCE), FILE))
    assert (surface.kind, surface.name, surface.line) == (TOOL_CALL, "lookup_user", 5)


def test_finds_tool_constructor_and_prefers_its_name_keyword() -> None:
    """A Tool(...) constructor is named by its name keyword, and keeps its import module."""
    surface = only(find_tool_calls(parse(TOOL_CONSTRUCTOR_SOURCE), FILE))
    assert (surface.kind, surface.name, surface.line) == (TOOL_CALL, "GetUserTransactions", 3)
    assert surface.module == "langchain.agents"


def test_finds_tool_subclass() -> None:
    """A class subclassing a framework tool base is reported at the class line."""
    surface = only(find_tool_calls(parse(TOOL_SUBCLASS_SOURCE), FILE))
    assert (surface.kind, surface.name, surface.line) == (TOOL_CALL, "ShellRunner", 4)


# --- Data sources ----------------------------------------------------------
def test_finds_outbound_request_as_data_source() -> None:
    """An outbound http call is reported as a DATA_SOURCE at its own line."""
    surface = only(find_data_sources(parse(DATA_SOURCE_SOURCE), FILE))
    assert (surface.kind, surface.name, surface.line) == (DATA_SOURCE, "requests.get", 3)
    assert surface.module == "requests"


def test_finds_web_route_handler_as_data_source() -> None:
    """A route handler is reported as a DATA_SOURCE because it receives request input."""
    surface = only(find_data_sources(parse(ROUTE_SOURCE), FILE))
    assert (surface.kind, surface.name, surface.line) == (DATA_SOURCE, "chat", 2)


# --- Detector independence -------------------------------------------------
@pytest.mark.parametrize(
    "detector, source",
    [
        (find_prompt_templates, PROMPT_CALL_SOURCE),
        (find_prompt_templates, PROMPT_STRING_SOURCE),
        (find_agent_defs, AGENT_SOURCE),
        (find_tool_calls, TOOL_DECORATOR_SOURCE),
        (find_tool_calls, TOOL_CONSTRUCTOR_SOURCE),
        (find_tool_calls, TOOL_SUBCLASS_SOURCE),
        (find_data_sources, DATA_SOURCE_SOURCE),
        (find_data_sources, ROUTE_SOURCE),
    ],
)
def test_other_detectors_ignore_this_construct(detector, source: str) -> None:
    """Only the owning detector reports a construct; the other three return nothing."""
    tree = parse(source)
    found = {other.__name__: other(tree, FILE) for other in other_detectors(detector)}
    assert not [name for name, surfaces in found.items() if surfaces], found


PROMPT_FORMAT_SOURCE = '''
from langchain.chains import LLMChain
def build(question):
    prompt = p2sql_template.format(question=question)
    return LLMChain(prompt=prompt)
'''

PROMPT_CONCAT_SOURCE = '''
def build(role):
    system_prompt = "You are " + role
    return system_prompt
'''

NON_TEXT_PROMPT_SOURCE = '''
def build():
    prompt_index = 1 + 2
    persona_list = [1, 2] + [3]
    return prompt_index, persona_list
'''


def test_prompt_built_by_format_is_found() -> None:
    """A prompt assembled with .format() is a prompt surface, not just a literal."""
    found = find_prompt_templates(ast.parse(PROMPT_FORMAT_SOURCE), "app.py")
    assembled = [s for s in found if s.name == "prompt"]
    assert len(assembled) == 1
    assert assembled[0].line == 4
    assert "formatted string" in assembled[0].detail


def test_prompt_built_by_concatenation_is_found() -> None:
    """A prompt assembled by joining strings is a prompt surface."""
    found = find_prompt_templates(ast.parse(PROMPT_CONCAT_SOURCE), "app.py")
    assert [s.name for s in found] == ["system_prompt"]
    assert "concatenated string" in found[0].detail


def test_prompt_named_non_text_is_ignored() -> None:
    """A prompt-shaped name holding numbers or lists is not a prompt surface."""
    assert find_prompt_templates(ast.parse(NON_TEXT_PROMPT_SOURCE), "app.py") == []


BOTH_ROUTES_SOURCE = '''
@app.route("/x")
def flask_handler(): pass

@app.post("/y")
def fastapi_handler(): pass
'''


def test_route_handlers_are_data_sources_with_readable_detail() -> None:
    """Both Flask @app.route and FastAPI @app.post handlers read as request inputs."""
    found = {s.name: s.detail for s in find_data_sources(ast.parse(BOTH_ROUTES_SOURCE), "api.py")}
    assert found["flask_handler"] == "http route input"
    assert found["fastapi_handler"] == "http post route input"
