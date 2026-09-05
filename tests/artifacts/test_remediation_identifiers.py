r"""Which of the app's names advice may not quote back, and how narrowly they match.

The list is only half of it. Matching is on whole words, and that is the rule
most likely to be wrong in either direction: too loose and a component named
`os` condemns the word "chosen", too tight and a leaked identifier walks
through. Both directions are asserted for each case.

A name split by formatting is the tight direction failing: `cursor.\<newline>
execute(sql)` parses, calls the app's own `cursor.execute`, and reads as two
unrelated fragments. The check therefore also matches a normalised copy, so the
tests below pin both the evasions it now refuses and the off positions where
rejoining must invent nothing.
"""

from artifacts.advice_rules import _joined, app_identifiers, judge
from artifacts.remediation import NAMES_APP_IDENTIFIER, REJECTED, WRITTEN
from remediation_fixtures import CLEAN_CODE, CLEAN_GUIDANCE, finding_record, snippet

COMPONENT = "langchain-community"
PURL = "pkg:pypi/langchain-community@0.2.1"
MODULE = "agent_runtime"

APP_MODULES = ("tools", "utils")

# The app's own database call, and the two ways formatting can hide it.
DB_CALL = "cursor.execute"
SPLIT_BY_CONTINUATION = "cursor.\\\n    execute(sql)"
SPLIT_BY_SPACED_DOT = "cursor . execute(sql)"
REJOINED = "cursor.execute(sql)"


def judge_code(finding: dict, code: str, module_names: tuple[str, ...] = ()) -> tuple:
    """Judge one snippet against a given finding, so each test states its own evidence."""
    return judge(finding, CLEAN_GUIDANCE, [snippet(code)], module_names)


def test_every_evidence_field_becomes_a_forbidden_identifier() -> None:
    """The five fields a finding cites are exactly what makes a snippet applicable here."""
    finding = finding_record(component_name=COMPONENT, purl=PURL, module=MODULE)
    assert set(app_identifiers(finding)) >= {
        "ShellTool", "app/agent.py", COMPONENT, PURL, MODULE}


def test_a_paths_basename_is_forbidden_as_well_as_the_path() -> None:
    """A snippet naming `agent.py` is as applicable as one naming `app/agent.py`."""
    assert "agent.py" in app_identifiers(finding_record())


def test_a_null_evidence_field_contributes_no_identifier() -> None:
    """A finding with no component must not forbid the string "None"."""
    assert "None" not in app_identifiers(finding_record())


def test_the_apps_own_module_names_are_included() -> None:
    """They are not in the finding, so the caller passes them in beside it."""
    assert set(app_identifiers(finding_record(), APP_MODULES)) >= set(APP_MODULES)


def test_the_identifier_list_is_sorted_and_free_of_duplicates() -> None:
    """It reaches the prompt as text, so two runs must produce the same string."""
    identifiers = app_identifiers(finding_record(module="ShellTool"), ("ShellTool",))
    assert identifiers == sorted(set(identifiers))


def test_a_finding_citing_nothing_forbids_nothing() -> None:
    """An empty list is the honest answer, not a crash and not a wildcard."""
    assert app_identifiers({}) == []


def test_a_short_component_name_does_not_condemn_a_longer_word() -> None:
    """The `os` case: matching on substrings would refuse the word "chosen"."""
    finding = finding_record(component_name="os")
    assert judge_code(finding, "settings = chosen_defaults()") == (WRITTEN, None, None)


def test_a_short_component_name_still_matches_itself() -> None:
    """The other direction: narrow matching must not let the real name through."""
    finding = finding_record(component_name="os")
    assert judge_code(finding, "import os") == (REJECTED, NAMES_APP_IDENTIFIER, "code")


def test_a_short_component_name_matches_when_it_is_the_qualifier() -> None:
    """`os.path.join` names `os`, so a trailing dot is a word boundary, not an escape."""
    finding = finding_record(component_name="os")
    assert judge_code(finding, "target = os.path.join(root, name)") == (
        REJECTED, NAMES_APP_IDENTIFIER, "code")


def test_a_dotted_identifier_does_not_match_a_differently_qualified_one() -> None:
    """`yaml.load` is not present in `yaml.safe_load`, and must not be read as if it were."""
    finding = finding_record(surface_name="yaml.load")
    assert judge_code(finding, "data = yaml.safe_load(text)") == (WRITTEN, None, None)


def test_a_dotted_identifier_matches_itself_exactly() -> None:
    """The same rule must still catch the call the finding is actually about."""
    finding = finding_record(surface_name="yaml.load")
    assert judge_code(finding, "data = yaml.load(text)") == (
        REJECTED, NAMES_APP_IDENTIFIER, "code")


def test_a_bare_name_does_not_match_a_qualified_attribute() -> None:
    """A local module named `tools` must not condemn a library's `langchain.tools`."""
    assert judge_code(finding_record(), "from langchain.tools import Tool", APP_MODULES) == (
        WRITTEN, None, None)


def test_a_bare_name_matches_when_it_is_used_bare() -> None:
    """The same module used as the app uses it is exactly what must be refused."""
    assert judge_code(finding_record(), "import tools", APP_MODULES) == (
        REJECTED, NAMES_APP_IDENTIFIER, "code")


def test_an_identifier_inside_a_longer_identifier_is_not_a_match() -> None:
    """`ShellToolkit` is a different symbol, and refusing it would refuse generic advice."""
    assert judge_code(finding_record(), "runner = ShellToolkit()") == (WRITTEN, None, None)


def test_an_identifier_with_a_prefix_is_not_a_match() -> None:
    """A leading word character is a boundary on the other side of the token too."""
    assert judge_code(finding_record(), "runner = SafeShellTool()") == (WRITTEN, None, None)


def test_a_name_split_by_a_line_continuation_is_refused() -> None:
    r"""`cursor.\<newline>execute(sql)` parses and calls the app's own method."""
    finding = finding_record(surface_name=DB_CALL)
    assert judge_code(finding, SPLIT_BY_CONTINUATION) == (
        REJECTED, NAMES_APP_IDENTIFIER, "code")


def test_a_name_spaced_around_its_dot_is_refused() -> None:
    """`cursor . execute(sql)` is the same call with the whitespace moved."""
    finding = finding_record(surface_name=DB_CALL)
    assert judge_code(finding, SPLIT_BY_SPACED_DOT) == (
        REJECTED, NAMES_APP_IDENTIFIER, "code")


def test_a_generic_call_on_another_receiver_is_still_written() -> None:
    """`cur.execute` is the standard pattern, not the app's `cursor.execute`."""
    finding = finding_record(surface_name=DB_CALL)
    assert judge_code(finding, "cur.execute(sql, params)") == (WRITTEN, None, None)


def test_closing_a_spaced_dot_does_not_invent_a_match() -> None:
    """`result . fetchall()` rejoins to another receiver, so it names nothing of the app's."""
    finding = finding_record(surface_name="cursor.fetchall")
    assert judge_code(finding, "rows = result . fetchall()") == (WRITTEN, None, None)


def test_a_space_away_from_a_dot_joins_nothing() -> None:
    """Two spaced words in a message are not the identifier `ShellTool` written together."""
    message = 'if not approved(action):\n    raise PermissionError("Shell Tool: denied")'
    assert judge_code(finding_record(), message) == (WRITTEN, None, None)


def test_a_short_name_does_not_condemn_a_longer_word_after_rejoining() -> None:
    """The `os` case again, down the normalised path: `chosen . defaults()` is not `os`."""
    finding = finding_record(component_name="os")
    assert judge_code(finding, "settings = chosen . defaults()") == (WRITTEN, None, None)


def test_a_rejoined_dotted_name_still_matches_only_itself() -> None:
    """Rejoining a continuation yields `yaml.safe_load`, which is not `yaml.load`."""
    finding = finding_record(surface_name="yaml.load")
    assert judge_code(finding, "data = yaml.\\\n    safe_load(text)") == (WRITTEN, None, None)


def test_joined_rejoins_a_line_continuation() -> None:
    """The backslash and the indent that follows it are what hid the name."""
    assert _joined(SPLIT_BY_CONTINUATION) == REJOINED


def test_joined_closes_the_whitespace_around_a_dot() -> None:
    """A dot with spaces either side is the same attribute access without them."""
    assert _joined(SPLIT_BY_SPACED_DOT) == REJOINED


def test_joined_leaves_ordinary_code_byte_identical() -> None:
    """It runs on every snippet, so code with neither split must come back untouched."""
    assert _joined(CLEAN_CODE) == CLEAN_CODE


def test_a_name_split_across_brackets_is_refused() -> None:
    """A bracketed continuation calls the same thing, so it hides the name just as well.

    `(cursor\n    .fetchall())` parses and is the audited app's own call. It is
    the third shape a dotted name can be broken across lines in, after the
    backslash and the spaced dot, and the same rule covers all three.
    """
    bracketed = "rows = (cursor\n        .fetchall())"
    finding = finding_record(surface_name="cursor.fetchall")
    assert judge_code(finding, bracketed) == (REJECTED, NAMES_APP_IDENTIFIER, "code")
