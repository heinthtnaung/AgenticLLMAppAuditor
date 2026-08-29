"""Shared test data for the two comparison baselines in `src/baselines/`.

One tiny application whose line numbers are named constants, and one stand-in
for Syft's document. Both baselines are scored against the real corpus
elsewhere; these exist so a rule can be asserted at a line a reader can count,
and so Baseline B's unit tests never need Syft installed.

The Syft stand-ins are the recorded generator output in `dependency_fixtures`,
reused rather than re-invented: `JS_GENERATOR_SAMPLE` already lists one package
at two versions and another at three, which is exactly the duplicate-id trap
`component_names` exists to avoid.
"""

from pathlib import Path

import pytest

from deps import syft_runner

# One file holding one match per rule, so each line below is a single subject.
# The numbers are asserted, not derived: a test that recomputes the line it
# expects passes even when the rule reports the wrong one.
TINY_APP_FILE = "app.py"
PROMPT_LINE = 3
INPUT_LINE = 5
TOOL_LINE = 7
TOOL_NAME = "GetUserTransactions"
SQL_LINE = 13
AGENT_LINE = 15
TINY_APP_SOURCE = '''\
import os

system_msg = """You are a support agent."""

question = st.chat_input(placeholder="ask")

lookup_tool = Tool(
    name="GetUserTransactions",
    func=lookup,
)

def read(user_id):
    cursor.execute(f"SELECT * FROM t WHERE id = '{user_id}'")

executor = AgentExecutor.from_agent_and_tools(agent=agent, tools=[lookup_tool])
'''

# A file no rule matches, so "found nothing" can be told from "read nothing".
QUIET_FILE = "quiet.py"
QUIET_SOURCE = "total = 1 + 2\n"

# A tool whose own name sits four lines below the constructor, one past the
# lookahead. What the baseline reports there is the constructor text itself.
FAR_TOOL_FILE = "far.py"
FAR_TOOL_LINE = 1
FAR_TOOL_FALLBACK_NAME = "Tool"
FAR_TOOL_SOURCE = '''\
far_tool = Tool(
    func=lookup,
    description="looks things up",
    return_direct=False,
    name="TooFarAway",
)
'''

# A tool whose own name sits on the third line below the constructor: the last
# line the lookahead reaches, and the one a narrower window would drop.
EDGE_TOOL_FILE = "edge.py"
EDGE_TOOL_LINE = 1
EDGE_TOOL_NAME = "EdgeOfWindow"
EDGE_TOOL_SOURCE = '''\
edge_tool = Tool(
    func=lookup,
    description="looks things up",
    name="EdgeOfWindow",
)
'''

# Bytes no UTF-8 decoder will read, in a file the walker still hands over.
UNDECODABLE_FILE = "binary.py"
UNDECODABLE_SOURCE = b'x = "\xff\xfe"\n'

# A Syft document holding a component with no name at all, which is neither a
# library to report nor an error to raise.
NAMELESS_SYFT_DOCUMENT = {"components": [{"type": "library", "version": "1.0.0"}]}
EMPTY_SYFT_DOCUMENT: dict = {}


def write_tiny_app(root: Path) -> str:
    """Write the one-match-per-rule app and return its repository path."""
    (root / TINY_APP_FILE).write_text(TINY_APP_SOURCE, encoding="utf-8")
    return str(root)


def stub_syft(monkeypatch: pytest.MonkeyPatch, document: dict) -> list[Path]:
    """Answer Syft with a recorded document, and return the list of directories asked about."""
    asked: list[Path] = []

    def fake_scan(app_dir: Path) -> dict:
        asked.append(app_dir)
        return document

    monkeypatch.setattr(syft_runner, "scan", fake_scan)
    return asked


def require_syft() -> None:
    """Skip a test that needs the real generator, rather than failing without it."""
    if not syft_runner.is_available():
        pytest.skip("syft is not installed - see the README prerequisites")
