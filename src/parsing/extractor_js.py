"""Parses JavaScript and TypeScript with tree-sitter and runs the JS detectors."""

from pathlib import Path

import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

from detectors.data_sources_js import find_data_sources
from detectors.detectors_js import (
    find_agent_defs,
    find_prompt_templates,
    find_tool_calls,
)
from artifacts.skipped_file import UNPARSEABLE_SYNTAX, UnreadableSource
from parsing.languages import JAVASCRIPT, TSX_GRAMMAR, TYPESCRIPT, grammar_of
from artifacts.surface import Surface

DETECTORS = (find_prompt_templates, find_agent_defs, find_tool_calls, find_data_sources)

# Built once: compiling a grammar on every file would be wasteful.
GRAMMARS = {
    JAVASCRIPT: Language(tree_sitter_javascript.language()),
    TYPESCRIPT: Language(tree_sitter_typescript.language_typescript()),
    TSX_GRAMMAR: Language(tree_sitter_typescript.language_tsx()),
}


def parse_source(source: bytes, path: Path) -> Node:
    """Parse one file, failing loudly if the grammar could not make sense of it.

    tree-sitter never raises: it returns a tree containing ERROR nodes. Left
    unchecked, a malformed file would silently yield zero surfaces.
    """
    tree = Parser(GRAMMARS[grammar_of(str(path))]).parse(source)
    if tree.root_node.has_error:
        raise UnreadableSource(
            f"cannot parse {path.name}: the file is not valid {grammar_of(str(path))}",
            UNPARSEABLE_SYNTAX,
        )
    return tree.root_node


def extract_file(path: Path, file_label: str) -> list[Surface]:
    """Run all four JS detectors over one file, labelled by its repo-relative path."""
    source = path.read_bytes()
    root = parse_source(source, path)
    found = []
    for detector in DETECTORS:
        found.extend(detector(root, file_label, source))
    return found
