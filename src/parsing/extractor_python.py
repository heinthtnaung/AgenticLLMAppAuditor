"""Parses Python with the standard library's ast and runs the Python detectors."""

import ast
import tokenize
from pathlib import Path

from detectors.detectors import (
    find_agent_defs,
    find_data_sources,
    find_prompt_templates,
    find_tool_calls,
)
from artifacts.surface import Surface

DETECTORS = (find_prompt_templates, find_agent_defs, find_tool_calls, find_data_sources)


def parse_file(path: Path) -> ast.AST:
    """Parse one Python file, naming the file if its syntax or encoding is invalid."""
    try:
        with tokenize.open(path) as handle:
            source = handle.read()
        return ast.parse(source, filename=str(path))
    except SyntaxError as error:
        raise SyntaxError(f"cannot parse {path}: {error.msg} (line {error.lineno})") from error


def extract_file(path: Path, file_label: str) -> list[Surface]:
    """Run all four Python detectors over one file, labelled by its repo-relative path."""
    tree = parse_file(path)
    found = []
    for detector in DETECTORS:
        found.extend(detector(tree, file_label))
    return found
