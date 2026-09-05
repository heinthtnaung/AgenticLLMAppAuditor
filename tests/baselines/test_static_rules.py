"""Baseline A matches its rules over raw text, and says so at the right line.

The line numbers here are the point. A grep baseline that finds the right file
and the wrong line scores zero against a key that anchors on lines, so every
test below names the line it expects rather than counting the list.
"""

from pathlib import Path

import pytest

from baseline_fixtures import (
    AGENT_LINE,
    EDGE_TOOL_FILE,
    EDGE_TOOL_LINE,
    EDGE_TOOL_NAME,
    EDGE_TOOL_SOURCE,
    FAR_TOOL_FALLBACK_NAME,
    FAR_TOOL_FILE,
    FAR_TOOL_LINE,
    FAR_TOOL_SOURCE,
    INPUT_LINE,
    PROMPT_LINE,
    QUIET_FILE,
    QUIET_SOURCE,
    SQL_LINE,
    TINY_APP_FILE,
    TOOL_LINE,
    TOOL_NAME,
    UNDECODABLE_FILE,
    UNDECODABLE_SOURCE,
    write_tiny_app,
)
from baselines.rules import RULES, TOOL_NAME_LOOKAHEAD
from artifacts.skipped_file import UNDECODABLE_BYTES
from baselines.static_rules import CHECK_NAMES, scan_repo, unreadable_files
from evaluation.grading import LINE_TOLERANCE

# What the one-match-per-rule app must produce: rule -> (line, surface name).
EXPECTED = {
    "grep_prompt_defines_policy": (PROMPT_LINE, "system_msg"),
    "grep_untrusted_input": (INPUT_LINE, "st.chat_input"),
    "grep_free_form_tool": (TOOL_LINE, TOOL_NAME),
    "grep_sql_string_building": (SQL_LINE, "cursor.execute"),
    "grep_agent_without_audit": (AGENT_LINE, "AgentExecutor.from_agent_and_tools"),
}

# The OWASP class each rule reports, from the 2025 list.
EXPECTED_CLASSES = {
    "grep_prompt_defines_policy": "LLM01",
    "grep_untrusted_input": "LLM01",
    "grep_free_form_tool": "LLM06",
    "grep_sql_string_building": "LLM02",
    "grep_agent_without_audit": "AUDITABILITY",
}

NESTED_DIR = "src/agent"


def by_rule(root: Path) -> dict[str, tuple[int, str]]:
    """Scan a repository and index what each rule reported, for the assertions below."""
    return {f.rule_id: (f.line, f.surface_name) for f in scan_repo(str(root))}


@pytest.fixture
def tiny_app(tmp_path: Path) -> dict[str, tuple[int, str]]:
    """Scan the one-match-per-rule app once and share the result."""
    write_tiny_app(tmp_path)
    return by_rule(tmp_path)


def test_finds_the_prompt_assignment_and_names_the_variable(tiny_app) -> None:
    """`system_msg = ...` is what the key calls a PROMPT_TEMPLATE named system_msg."""
    assert tiny_app["grep_prompt_defines_policy"] == EXPECTED["grep_prompt_defines_policy"]


def test_finds_the_untrusted_input_call_and_names_it(tiny_app) -> None:
    """The name reported is the call itself, `st.chat_input`, not the variable it fills."""
    assert tiny_app["grep_untrusted_input"] == EXPECTED["grep_untrusted_input"]


def test_finds_the_interpolated_sql_and_names_the_cursor_call(tiny_app) -> None:
    """`cursor.execute(f"` is the LLM02 rule's whole subject."""
    assert tiny_app["grep_sql_string_building"] == EXPECTED["grep_sql_string_building"]


def test_finds_the_agent_executor_construction(tiny_app) -> None:
    """The AUDITABILITY rule anchors on the constructor line, where the key does."""
    assert tiny_app["grep_agent_without_audit"] == EXPECTED["grep_agent_without_audit"]


def test_names_a_tool_by_the_name_argument_below_its_constructor(tiny_app) -> None:
    """The line stays on `Tool(`; only the name is read from the argument beneath it."""
    assert tiny_app["grep_free_form_tool"] == EXPECTED["grep_free_form_tool"]


def test_a_tool_name_on_the_last_line_of_the_lookahead_is_still_found(tmp_path: Path) -> None:
    """Three lines below is inside the window, so a narrower one would lose the tool's name."""
    (tmp_path / EDGE_TOOL_FILE).write_text(EDGE_TOOL_SOURCE, encoding="utf-8")
    assert by_rule(tmp_path)["grep_free_form_tool"] == (EDGE_TOOL_LINE, EDGE_TOOL_NAME)


def test_the_lookahead_is_the_same_window_the_join_rule_allows() -> None:
    """The module claims the three lines are not a special case invented for it."""
    assert TOOL_NAME_LOOKAHEAD == LINE_TOLERANCE


def test_a_tool_name_past_the_lookahead_falls_back_to_the_constructor_text(
        tmp_path: Path) -> None:
    """Four lines down is outside the window, so the match names itself instead."""
    (tmp_path / FAR_TOOL_FILE).write_text(FAR_TOOL_SOURCE, encoding="utf-8")
    assert by_rule(tmp_path)["grep_free_form_tool"] == (FAR_TOOL_LINE, FAR_TOOL_FALLBACK_NAME)


def test_every_rule_reports_the_owasp_class_written_beside_it(tmp_path: Path) -> None:
    """The class is a constant on the rule, so a match can never reclassify itself."""
    write_tiny_app(tmp_path)
    assert {f.rule_id: f.owasp_id for f in scan_repo(str(tmp_path))} == EXPECTED_CLASSES


def test_every_rule_in_the_list_is_exercised_by_this_app(tiny_app) -> None:
    """Guard: a rule added without a fixture line would be tested by nothing here."""
    assert set(tiny_app) == set(CHECK_NAMES) == {rule.rule_id for rule in RULES}


def test_findings_are_reported_against_repo_relative_posix_paths(tmp_path: Path) -> None:
    """The key's `file` is repo-relative, so an absolute path would match nothing."""
    nested = tmp_path / NESTED_DIR
    nested.mkdir(parents=True)
    write_tiny_app(nested)
    assert {f.file for f in scan_repo(str(tmp_path))} == {f"{NESTED_DIR}/{TINY_APP_FILE}"}


def test_a_file_matching_no_rule_produces_no_finding(tmp_path: Path) -> None:
    """Silence has to be reachable, or every assertion above is about a rule that always fires."""
    (tmp_path / QUIET_FILE).write_text(QUIET_SOURCE, encoding="utf-8")
    assert scan_repo(str(tmp_path)) == []


def test_an_empty_repository_produces_no_finding(tmp_path: Path) -> None:
    """Nothing to read is not an error for this baseline; it is an empty result."""
    assert scan_repo(str(tmp_path)) == []


def test_every_finding_id_is_unique_so_the_document_will_accept_them(tmp_path: Path) -> None:
    """`build_findings_document` refuses duplicate ids, so the scan must not produce any."""
    write_tiny_app(tmp_path)
    ids = [finding.id for finding in scan_repo(str(tmp_path))]
    assert len(set(ids)) == len(ids)


def test_a_missing_repository_path_is_named_in_the_error(tmp_path: Path) -> None:
    """Rule 8: a path that does not exist fails loudly rather than scanning nothing."""
    missing = tmp_path / "no-such-app"
    with pytest.raises(FileNotFoundError) as raised:
        scan_repo(str(missing))
    assert str(missing) in str(raised.value)


def test_a_file_given_instead_of_a_repository_is_rejected(tmp_path: Path) -> None:
    """A path that is not a directory is the other half of the same guard."""
    write_tiny_app(tmp_path)
    with pytest.raises(NotADirectoryError):
        scan_repo(str(tmp_path / TINY_APP_FILE))


def test_an_undecodable_file_costs_that_file_and_not_the_scan(tmp_path: Path) -> None:
    """Bytes no decoder reads yield nothing, and the readable file beside it still matches."""
    write_tiny_app(tmp_path)
    (tmp_path / UNDECODABLE_FILE).write_bytes(UNDECODABLE_SOURCE)
    assert {f.file for f in scan_repo(str(tmp_path))} == {TINY_APP_FILE}


def test_an_undecodable_file_is_recorded_rather_than_dropped(tmp_path: Path) -> None:
    """A file the rules never read must not read as a file the rules cleared.

    The auditor records the same thing, for the same reason: silence about an
    unread file turns "never examined" into "examined and clean", which is an
    error in this system's own favour.
    """
    write_tiny_app(tmp_path)
    (tmp_path / UNDECODABLE_FILE).write_bytes(UNDECODABLE_SOURCE)
    skipped = unreadable_files(str(tmp_path))
    assert [(s.file, s.reason) for s in skipped] == [(UNDECODABLE_FILE, UNDECODABLE_BYTES)]


def test_a_readable_repository_skips_nothing(tmp_path: Path) -> None:
    """The off position: an empty skipped list is a claim, so it must be earned."""
    write_tiny_app(tmp_path)
    assert unreadable_files(str(tmp_path)) == []
