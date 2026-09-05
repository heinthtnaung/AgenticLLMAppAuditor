"""One mixed-language LLM application, written into `tmp_path` by the tests that need it.

The pinned corpus was removed on 2026-09-04, and several safety guards got
their realism from it: the byte-identity check, the offline check, the whole
audit workflow. They need an audited tree that really yields surfaces in both
languages, joins to a component, and produces findings from more than one
check -- otherwise "no socket was opened" and "no file was changed" are claims
about a run that did nothing.

**Its inputs were chosen by the same author as the code**, which the corpus's
were not. What that costs is worth saying plainly: nothing here is oversized,
non-UTF-8, malformed, symlinked or shaped in a way nobody foresaw, so a defect
that only appears on one of those is not caught by a test using this. The
counts below are asserted as literals for the same reason -- an empty run must
not be able to pass as a clean one.
"""

from pathlib import Path

from artifacts.surface import AGENT_DEF, DATA_SOURCE, PROMPT_TEMPLATE, TOOL_CALL

APP_NAME = "mixed-app"

PYTHON_FILE = "agent.py"
# Imports three real packages the recorded SBOM in `dependency_fixtures` lists,
# so the surfaces below have something to join to rather than a guess. Lines 9
# and 10 are a real source-to-sink flow: an end user's question, unchecked,
# handed straight to the agent -- so the taint trace has something to follow.
# The lookup at the bottom builds its query by interpolation, so the query
# check has a subject too and a whole-app audit produces findings from five
# checks rather than two. `cursor` is a parameter, which is why that surface
# resolves to no package: the mapping counts are asserted against that. The
# `AgentExecutor` on line 8 is built with no `callbacks=`, which is what gives
# the auditability check its subject -- adding one would silence it and drop
# `MIXED_APP_FINDINGS` back to four.
PYTHON_SOURCE = '''import streamlit as st
from langchain.agents import AgentExecutor
from langchain_community.tools import ShellTool
from langchain.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_template("You are a support agent. {question}")
shell = ShellTool()
agent = AgentExecutor.from_agent_and_tools(agent=None, tools=[shell])

question = st.chat_input("Ask the support agent")
answer = agent(question)


def ticket_history(cursor, user):
    return cursor.execute(f"SELECT * FROM tickets WHERE user = '{user}'")
'''

# Line 10 above, where the untrusted value enters. The taint check anchors its
# finding on the source rather than on the sink it reached, so this is the line
# a test asserts against.
UNTRUSTED_INPUT_LINE = 10

# Line 15, where the query is built by interpolation. The query check anchors
# its finding on that surface, so this is the line a test asserts against.
UNSAFE_QUERY_LINE = 15

# The agent surface's name and line, for the tests that assert one located
# surface rather than a count.
AGENT_SURFACE_NAME = "AgentExecutor.from_agent_and_tools"
AGENT_SURFACE_LINE = 8

TYPESCRIPT_FILE = "web.ts"
# An npm import, so the second backend is exercised and the mapping has to
# refuse a cross-ecosystem join rather than making one.
TYPESCRIPT_SOURCE = '''import { ChatOpenAI } from "@langchain/openai";

const model = new ChatOpenAI({ model: "gpt-4o-mini" });

export async function answer(question: string) {
  return model.invoke(`You are a support agent. ${question}`);
}
'''

# Five Python surfaces (prompt, tool, agent, the untrusted input and the
# database query) and one TypeScript agent.
MIXED_APP_SURFACES = 6

# All four surface kinds, imported from the module that declares them rather
# than respelled: the Python file holds three plus the input feeding them, and
# the TypeScript file holds a second agent.
MIXED_APP_KINDS = {PROMPT_TEMPLATE, TOOL_CALL, AGENT_DEF, DATA_SOURCE}

# What the AIBOM makes of those surfaces: the two agents and the tool. A prompt
# template and an input are not AI components, so they are not counted.
MIXED_APP_AI_COMPONENTS = 3

# Four of the five Python surfaces, each resolving to a package the recorded
# SBOM declares. The query surface is a call on a parameter, so no import names
# its package; the TypeScript one is npm, which that PyPI SBOM cannot answer for.
MIXED_APP_JOINS = 4

# One from the permission check (ShellTool), one from the supply-chain check
# (the undeclared npm import), one from the taint check (the question reaching
# the agent), one from the query check (the interpolated lookup) and one from
# the auditability check (the `AgentExecutor` on line 8 is built with no
# `callbacks=`), so no single check can carry this alone. The tests that use
# this assert the five rule_ids, not just the total: five findings from one
# check would otherwise pass.
MIXED_APP_FINDINGS = 5


def write_mixed_app(tmp_path: Path) -> Path:
    """Write the Python and TypeScript files of the app and return its repository path."""
    repo = tmp_path / APP_NAME
    repo.mkdir()
    (repo / PYTHON_FILE).write_text(PYTHON_SOURCE, encoding="utf-8")
    (repo / TYPESCRIPT_FILE).write_text(TYPESCRIPT_SOURCE, encoding="utf-8")
    return repo
