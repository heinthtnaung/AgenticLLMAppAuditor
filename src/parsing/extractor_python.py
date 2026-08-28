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
from artifacts.skipped_file import UNDECODABLE_BYTES, UNPARSEABLE_SYNTAX, UnreadableSource
from artifacts.surface import Surface

DETECTORS = (find_prompt_templates, find_agent_defs, find_tool_calls, find_data_sources)


def read_source(path: Path) -> str:
    """Read one Python file as text, using whichever encoding it declares.

    Kept separate from parsing because the stdlib reports a bad encoding and a
    bad statement the same way — both are SyntaxError — so only the call site
    can tell the two skip reasons apart.
    """
    try:
        with tokenize.open(path) as handle:
            return handle.read()
    except (SyntaxError, UnicodeDecodeError) as error:
        raise UnreadableSource(
            f"cannot decode {path.name}: it is not valid text in its declared encoding",
            UNDECODABLE_BYTES,
        ) from error


def parse_file(path: Path) -> ast.AST:
    """Parse one Python file, naming the file and line if its syntax is invalid."""
    source = read_source(path)
    try:
        # Named by file, not full path: an absolute path must never reach an artifact.
        return ast.parse(source, filename=path.name)
    except SyntaxError as error:
        raise UnreadableSource(
            f"cannot parse {path.name}: {error.msg} (line {error.lineno})",
            UNPARSEABLE_SYNTAX, error.lineno,
        ) from error


def extract_file(path: Path, file_label: str) -> list[Surface]:
    """Run all four Python detectors over one file, labelled by its repo-relative path."""
    tree = parse_file(path)
    found = []
    for detector in DETECTORS:
        found.extend(detector(tree, file_label))
    return found
