"""Shared helpers for the JS detector tests: parse a TypeScript snippet, inspect the result."""

import textwrap

from detectors.data_sources_js import find_data_sources
from detectors.detectors_js import (
    find_agent_defs,
    find_prompt_templates,
    find_tool_calls,
)
from parsing.extractor_js import GRAMMARS
from parsing.languages import TYPESCRIPT
from tree_sitter import Node, Parser

FILE = "app/snippet.ts"

ALL_DETECTORS = (find_prompt_templates, find_agent_defs, find_tool_calls, find_data_sources)


def parse(source: str) -> tuple[Node, bytes]:
    """Parse a snippet with the TypeScript grammar, keeping its line numbers as written."""
    text = textwrap.dedent(source).lstrip("\n").encode("utf-8")
    return Parser(GRAMMARS[TYPESCRIPT]).parse(text).root_node, text


def run(detector, source: str) -> list:
    """Run one JS detector over a snippet and return the surfaces it found."""
    root, text = parse(source)
    return detector(root, FILE, text)


def only(surfaces: list) -> object:
    """Return the single surface a detector found, failing if it found anything else."""
    assert len(surfaces) == 1, f"expected exactly one surface, got {[s.name for s in surfaces]}"
    return surfaces[0]


def other_detectors(detector) -> list:
    """Return every detector except the given one, to prove they stay independent."""
    return [other for other in ALL_DETECTORS if other is not detector]
