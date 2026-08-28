"""The Surface data model: validation, identity, and stable JSON output."""

import json

import pytest
from artifacts.skipped_file import TOO_LARGE, UNPARSEABLE_SYNTAX, SkippedFile
from parsing.languages import JAVASCRIPT, PYTHON
from artifacts.surface import (
    AGENT_DEF,
    PROMPT_TEMPLATE,
    SCHEMA_VERSION,
    TOOL_CALL,
    Surface,
    deduplicate,
    surfaces_to_json,
)

# The schema version this test file was written against.
EXPECTED_SCHEMA_VERSION = 3


def _prompt(line: int = 12, detail: str = "prompt string assigned to system_msg") -> Surface:
    """Build a valid prompt-template surface for the tests to work with."""
    return Surface(PROMPT_TEMPLATE, "system_msg", "main.py", line, PYTHON, detail)


def test_id_has_the_documented_format() -> None:
    """A surface id is file:line:kind:name, the handle later phases use."""
    assert _prompt().id == "main.py:12:PROMPT_TEMPLATE:system_msg"


def test_json_output_is_order_independent() -> None:
    """The same surfaces in a different order serialise byte-identically."""
    agent = Surface(AGENT_DEF, "AgentExecutor", "main.py", 40, PYTHON, "agent built")
    surfaces = [_prompt(), agent]
    assert surfaces_to_json(surfaces, []) == surfaces_to_json(list(reversed(surfaces)), [])


def test_json_document_carries_schema_version_and_count() -> None:
    """The artifact document reports its schema version and surface count."""
    document = json.loads(surfaces_to_json([_prompt()], []))
    assert document["schema_version"] == SCHEMA_VERSION
    assert document["surface_count"] == len(document["surfaces"]) == 1


def test_serialised_schema_version_is_three() -> None:
    """Recording the files a scan could not read bumped the artifact contract to 3."""
    assert json.loads(surfaces_to_json([_prompt()], []))["schema_version"] == EXPECTED_SCHEMA_VERSION


def test_json_record_includes_the_id() -> None:
    """Each serialised record carries the surface's id alongside its fields."""
    record = json.loads(surfaces_to_json([_prompt()], []))["surfaces"][0]
    assert record["id"] == _prompt().id
    assert record["module"] == ""


def test_json_record_includes_the_language() -> None:
    """Each serialised record names the language its file is written in."""
    record = json.loads(surfaces_to_json([_prompt()], []))["surfaces"][0]
    assert record["language"] == PYTHON


def test_duplicates_differing_only_in_detail_collapse() -> None:
    """detail is descriptive only, so it does not create a second surface."""
    unique = deduplicate([_prompt(), _prompt(detail="found again by another pass")])
    assert len(unique) == 1


def test_different_lines_are_different_surfaces() -> None:
    """Two records at different lines are two surfaces."""
    assert len(deduplicate([_prompt(line=12), _prompt(line=13)])) == 2


def test_unknown_kind_is_rejected() -> None:
    """A kind outside the four declared kinds fails loudly."""
    with pytest.raises(ValueError, match="unknown surface kind"):
        Surface("PROMPT", "system_msg", "main.py", 12, PYTHON, "detail")


def test_unknown_language_is_rejected() -> None:
    """A language outside the declared vocabulary fails loudly."""
    with pytest.raises(ValueError, match="unknown language"):
        Surface(PROMPT_TEMPLATE, "system_msg", "main.rb", 12, "ruby", "detail")


def test_every_declared_language_is_accepted() -> None:
    """A surface may be built for any language the auditor can read."""
    surface = Surface(TOOL_CALL, "lookup", "app.js", 1, JAVASCRIPT, "tool defined")
    assert surface.language == JAVASCRIPT


def test_empty_name_is_rejected() -> None:
    """A surface with no name cannot be reported or reviewed, so it is rejected."""
    with pytest.raises(ValueError, match="name must not be empty"):
        Surface(TOOL_CALL, "", "main.py", 12, PYTHON, "detail")


def test_empty_file_is_rejected() -> None:
    """A surface with no file has no location, so it is rejected."""
    with pytest.raises(ValueError, match="file must not be empty"):
        Surface(TOOL_CALL, "lookup", "", 12, PYTHON, "detail")


def test_line_below_one_is_rejected() -> None:
    """Line numbers are 1-indexed, so 0 is invalid."""
    with pytest.raises(ValueError, match="line must be 1 or greater"):
        Surface(TOOL_CALL, "lookup", "main.py", 0, PYTHON, "detail")


@pytest.mark.parametrize("bad_file", ["/abs/x.py", "a\\b.py"])
def test_non_repo_relative_file_is_rejected(bad_file: str) -> None:
    """Absolute and Windows-style paths are rejected so output stays machine-independent."""
    with pytest.raises(ValueError, match="repo-relative posix path"):
        Surface(TOOL_CALL, "lookup", bad_file, 12, PYTHON, "detail")


def test_the_skipped_list_has_no_default() -> None:
    """A caller allowed to omit it would silently claim a complete scan, so it is required."""
    with pytest.raises(TypeError):
        surfaces_to_json([_prompt()])


def test_json_document_records_the_skipped_files() -> None:
    """The unreadable files travel in the same document as the surfaces."""
    document = json.loads(surfaces_to_json([_prompt()], [SkippedFile("bad.py", UNPARSEABLE_SYNTAX, 4)]))
    assert document["skipped_file_count"] == 1
    assert document["skipped_files"] == [{"file": "bad.py", "reason": UNPARSEABLE_SYNTAX, "line": 4}]


def test_skipped_output_is_order_independent() -> None:
    """Walk order must not show through: the same skips serialise byte-identically."""
    skips = [SkippedFile("b.py", TOO_LARGE), SkippedFile("a.py", UNPARSEABLE_SYNTAX, 2)]
    assert surfaces_to_json([], skips) == surfaces_to_json([], list(reversed(skips)))
