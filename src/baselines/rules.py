"""The regex rules Baseline A matches, written down before the code that runs them.

This is the "grep for the dangerous names" baseline: what a competent engineer
would write in an afternoon without this project. It reads **raw source text and
raw manifest text only** -- no syntax tree, no surface model, no SBOM, no
mapping. Those are this project's own work, and a baseline built on them is not
a baseline.

The rules are here, apart from the runner, so they can be read and argued with
on their own. A baseline that is quietly weakened once the numbers come out
close is worth nothing, and a rule list in a separate file is harder to weaken
without noticing.

Each rule names the surface its match identifies, because `matches_key` compares
`surface_kind` and `surface_name`. That is not borrowing the auditor's
extractor: a regex that matches `st.chat_input(` has genuinely named a data
source, which is exactly what a grep tool reports.
"""

import re
from dataclasses import dataclass

from artifacts.surface import AGENT_DEF, DATA_SOURCE, PROMPT_TEMPLATE, TOOL_CALL


@dataclass(frozen=True)
class Rule:
    """One regex rule: what it matches, what it reports, and what it names."""

    rule_id: str
    owasp_id: str
    title: str
    surface_kind: str
    pattern: re.Pattern
    # Which capture group holds the surface name; 0 means the whole match.
    name_group: int = 1


# Deliberately crude, and each one is the obvious grep a practitioner reaches
# for. They over-report by design -- that is what a baseline does, and the clean
# fixtures are where the cost of it shows up.
RULES = (
    Rule(
        "grep_prompt_defines_policy", "LLM01",
        "A prompt string carries instructions no code enforces",
        PROMPT_TEMPLATE,
        re.compile(r"^\s*(\w*(?:prompt|system_msg|instruction|persona)\w*)\s*=", re.I),
    ),
    Rule(
        "grep_untrusted_input", "LLM01",
        "Untrusted input is read and reaches the app unfiltered",
        DATA_SOURCE,
        re.compile(r"\b((?:st\.chat_input|st\.text_input|input|request\.form\.get))\s*\("),
    ),
    Rule(
        "grep_sql_string_building", "LLM02",
        "A SQL query is built by string interpolation",
        DATA_SOURCE,
        re.compile(r"\b((?:cursor|conn|db)\.execute)\s*\(\s*f[\"']"),
    ),
    Rule(
        "grep_agent_without_audit", "AUDITABILITY",
        "An agent executor is constructed with no audit sink named beside it",
        AGENT_DEF,
        re.compile(r"\b(AgentExecutor(?:\.\w+)?)\s*\("),
    ),
    Rule(
        "grep_free_form_tool", "LLM06",
        "A tool is exposed to the model with no authorisation check",
        TOOL_CALL,
        re.compile(r"\bTool\s*\("),
        name_group=0,
    ),
)

# A tool's own `name=` sits a line or two below `Tool(`, and the grading key
# anchors on the constructor line. Three lines is the same tolerance the join
# rule allows, so looking that far is not a special case invented here.
TOOL_NAME_PATTERN = re.compile(r"""name\s*=\s*["'](\w+)["']""")
TOOL_NAME_LOOKAHEAD = 3


def surface_name(rule: Rule, match: re.Match, following_lines: list[str]) -> str:
    """Name the surface a match identifies, looking ahead only for a tool's own name."""
    if rule.name_group != 0:
        return match.group(rule.name_group)
    for line in following_lines[:TOOL_NAME_LOOKAHEAD]:
        named = TOOL_NAME_PATTERN.search(line)
        if named:
            return named.group(1)
    return match.group(0).rstrip("( ")
