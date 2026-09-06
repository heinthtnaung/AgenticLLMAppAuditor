"""Task 1.7: what `extract_repo` and `extract_file` report, and what they refuse.

This file used to assert every surface named in a pinned app's
`ground_truth.json`. That corpus was removed, and with it the one input in the
suite whose surfaces were written down by someone other than the author of the
detectors. What is left is exercised over a tree the test writes, so its inputs
were chosen by the same author as the code: no oversized file, no non-UTF-8
source, no unforeseen framework idiom. `mixed_app_fixtures` states its counts as
literals so an empty extraction cannot pass as a clean one.
"""

import json

import pytest
from conftest import scan_to_json
from mixed_app_fixtures import (
    MIXED_APP_KINDS,
    MIXED_APP_SURFACES,
    PYTHON_FILE,
    TYPESCRIPT_FILE,
    write_mixed_app,
)
from parsing.extractor import extract_file, extract_repo
from parsing.extractor_js import parse_source
from parsing.extractor_python import parse_file
from artifacts.skipped_file import UnreadableSource
from artifacts.surface import PROMPT_TEMPLATE, SURFACE_KINDS


def test_extract_repo_finds_every_surface_in_the_written_app(tmp_path) -> None:
    """The count is a literal, so an extraction that found nothing fails here."""
    surfaces = extract_repo(str(write_mixed_app(tmp_path))).surfaces
    assert len(surfaces) == MIXED_APP_SURFACES


def test_extract_repo_returns_repo_relative_paths(tmp_path) -> None:
    """Extracted files are repo-relative posix paths, so output is machine-independent."""
    surfaces = extract_repo(str(write_mixed_app(tmp_path))).surfaces
    assert {surface.file for surface in surfaces} == {PYTHON_FILE, TYPESCRIPT_FILE}


def test_extract_repo_never_reports_an_absolute_path(tmp_path) -> None:
    """The tree sits under `tmp_path`, so a leaked absolute path would be visible."""
    surfaces = extract_repo(str(write_mixed_app(tmp_path))).surfaces
    assert not [s for s in surfaces if s.file.startswith("/") or "\\" in s.file]


def test_extract_repo_uses_only_known_kinds(tmp_path) -> None:
    """The written app holds all four declared kinds, and reports no fifth."""
    surfaces = extract_repo(str(write_mixed_app(tmp_path))).surfaces
    assert {surface.kind for surface in surfaces} == MIXED_APP_KINDS
    assert MIXED_APP_KINDS <= set(SURFACE_KINDS)


def test_extract_repo_on_repo_without_source_returns_empty(tmp_path) -> None:
    """A repository with no source files yields no surfaces rather than an error."""
    (tmp_path / "README.md").write_text("no code here\n", encoding="utf-8")
    assert extract_repo(str(tmp_path)).surfaces == []


def test_extract_file_uses_the_given_label(tmp_path) -> None:
    """extract_file records the caller's label, not the absolute path on disk."""
    source = tmp_path / "agent.py"
    source.write_text("system_prompt = \"be helpful\"\n", encoding="utf-8")
    surfaces = extract_file(source, "app/agent.py")
    assert [(s.file, s.line, s.name) for s in surfaces] == [("app/agent.py", 1, "system_prompt")]


def test_parse_file_names_the_file_with_broken_syntax(tmp_path) -> None:
    """An unparsable Python file raises UnreadableSource naming the file and line."""
    broken = tmp_path / "broken.py"
    broken.write_text("def oops(:\n", encoding="utf-8")
    with pytest.raises(UnreadableSource, match="broken.py"):
        parse_file(broken)


def test_parse_source_names_the_file_with_broken_typescript(tmp_path) -> None:
    """A malformed TypeScript file raises an error naming the file, never zero surfaces."""
    broken = tmp_path / "broken.ts"
    broken.write_text("function oops( {\n", encoding="utf-8")
    with pytest.raises(UnreadableSource, match="broken.ts"):
        parse_source(broken.read_bytes(), broken)


def test_extract_file_requires_a_file_label(tmp_path) -> None:
    """extract_file will not guess a label, so a misused call fails at the call site."""
    with pytest.raises(TypeError):
        extract_file(write_mixed_app(tmp_path) / PYTHON_FILE)


def test_extract_file_rejects_an_absolute_label(tmp_path) -> None:
    """An absolute label is refused outright rather than producing a machine-specific artifact."""
    path = write_mixed_app(tmp_path) / PYTHON_FILE
    with pytest.raises(ValueError, match="repo-relative"):
        extract_file(path, str(path))


def test_repeated_runs_produce_identical_bytes(tmp_path) -> None:
    """The same repository always serialises to the same bytes."""
    repo = str(write_mixed_app(tmp_path))
    assert scan_to_json(repo) == scan_to_json(repo)


# --- A whole application that keeps its prompts on the instance --------------
# The mixed app above holds its prompt in a module-level variable, so nothing in
# this file walked a class-based application until now. Two methods assign the
# same attribute, which is also the one thing the detector tests cannot show:
# `surfaces.json` deduplicates on (file, line, kind, name), so two prompts
# sharing a name have to survive as two records rather than collapse into one.
CLASS_APP_FILE = "support_agent.py"
CLASS_APP_SOURCE = '''class SupportAgent:
    def __init__(self, user):
        self.system_prompt = f"You are a support agent helping {user}."

    def escalate(self, user):
        self.system_prompt = f"You are escalating the ticket of {user}."
'''
CLASS_APP_PROMPT_LINES = (3, 6)


def test_prompts_held_on_a_class_reach_the_artifact(tmp_path) -> None:
    """Both attribute prompts are serialised, at their own lines and under their own name."""
    repo = tmp_path / "class-app"
    repo.mkdir()
    (repo / CLASS_APP_FILE).write_text(CLASS_APP_SOURCE, encoding="utf-8")
    document = json.loads(scan_to_json(str(repo)))
    prompts = [s for s in document["surfaces"] if s["kind"] == PROMPT_TEMPLATE]
    assert [(s["file"], s["line"], s["name"]) for s in prompts] == [
        (CLASS_APP_FILE, line, "system_prompt") for line in CLASS_APP_PROMPT_LINES
    ]
