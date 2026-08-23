"""Runs the four surface detectors over one file and over a whole repository."""

import ast
import tokenize
from pathlib import Path

from detectors import (
    find_agent_defs,
    find_data_sources,
    find_prompt_templates,
    find_tool_calls,
)
from repo_loader import list_python_files
from surface import Surface

# One entry per surface kind. Each detector is independent of the others.
DETECTORS = (find_prompt_templates, find_agent_defs, find_tool_calls, find_data_sources)


def parse_file(path: Path) -> ast.AST:
    """Parse one Python file, naming the file if its syntax is invalid."""
    try:
        with tokenize.open(path) as handle:
            source = handle.read()
        return ast.parse(source, filename=str(path))
    except SyntaxError as error:
        raise SyntaxError(f"cannot parse {path}: {error.msg} (line {error.lineno})") from error


def extract_file(path: Path, file_label: str) -> list[Surface]:
    """Run all four detectors over one Python file, labelled by its repo-relative path."""
    tree = parse_file(path)
    found = []
    for detector in DETECTORS:
        found.extend(detector(tree, file_label))
    return found


def extract_repo(repo_path: str) -> list[Surface]:
    """Run all four detectors over every Python file in the repository."""
    root = Path(repo_path)
    found = []
    for path in list_python_files(repo_path):
        found.extend(extract_file(path, path.relative_to(root).as_posix()))
    return found
