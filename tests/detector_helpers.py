"""Shared helpers for the detector tests: parse a snippet, inspect what came back."""

import ast
import textwrap

from detectors import (
    find_agent_defs,
    find_data_sources,
    find_prompt_templates,
    find_tool_calls,
)

FILE = "app/snippet.py"

# Sample sources, one per construct the detectors must recognise.
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

BOTH_ROUTES_SOURCE = '''
@app.route("/x")
def flask_handler(): pass

@app.post("/y")
def fastapi_handler(): pass
'''

ALL_DETECTORS = (find_prompt_templates, find_agent_defs, find_tool_calls, find_data_sources)


def parse(source: str) -> ast.AST:
    """Parse a snippet, keeping its line numbers as written after the leading newline."""
    return ast.parse(textwrap.dedent(source).lstrip("\n"))


def only(surfaces: list) -> object:
    """Return the single surface a detector found, failing if it found anything else."""
    assert len(surfaces) == 1, f"expected exactly one surface, got {[s.name for s in surfaces]}"
    return surfaces[0]


def other_detectors(detector) -> list:
    """Return every detector except the given one, to prove they stay independent."""
    return [other for other in ALL_DETECTORS if other is not detector]
