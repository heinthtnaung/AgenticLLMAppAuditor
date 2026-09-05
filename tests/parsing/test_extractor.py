"""Task 1.7: what `extract_repo` and `extract_file` report, and what they refuse.

This file used to assert every surface named in a pinned app's
`ground_truth.json`. That corpus was removed, and with it the one input in the
suite whose surfaces were written down by someone other than the author of the
detectors. What is left is exercised over a tree the test writes, so its inputs
were chosen by the same author as the code: no oversized file, no non-UTF-8
source, no unforeseen framework idiom. `mixed_app_fixtures` states its counts as
literals so an empty extraction cannot pass as a clean one.
"""

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
from artifacts.surface import SURFACE_KINDS


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
