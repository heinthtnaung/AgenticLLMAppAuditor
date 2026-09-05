"""The remediation document: one entry per finding, and three counts that never hide.

`status_counts` carries all three keys whether or not any is zero, so a reader
never subtracts one number from another to discover that nothing was refused.
The document also refuses to be built from two entries claiming one finding,
because the file is joined to `findings.json` on exactly that key.
"""

import json

import pytest

from artifacts.remediation import (
    ADVICE_STATUSES,
    NAMES_APP_IDENTIFIER,
    REJECTED,
    SCHEMA_VERSION,
    UNAVAILABLE,
    WRITTEN,
    build_remediation_document,
    remediation_to_json,
)
from remediation_fixtures import (
    FINDINGS_SCHEMA_VERSION,
    no_knowledge,
    rejected_entry,
    remediation_document,
    unavailable_entry,
    unavailable_run,
    used_run,
    written_entry,
)

FIRST = "a.py:1:TOOL_CALL:First:high_privilege_tool"
SECOND = "b.py:2:TOOL_CALL:Second:high_privilege_tool"
THIRD = "c.py:3:TOOL_CALL:Third:high_privilege_tool"


def mixed_document() -> dict:
    """A document holding one of each status, so every count is non-zero."""
    return remediation_document([
        written_entry(FIRST),
        rejected_entry(SECOND, NAMES_APP_IDENTIFIER),
        unavailable_entry(THIRD),
    ])


def test_the_document_reports_its_own_schema_version() -> None:
    """A reader checks the version before trusting any other field."""
    assert mixed_document()["schema_version"] == SCHEMA_VERSION


def test_the_document_names_the_findings_schema_it_was_written_from() -> None:
    """What invalidates this file, in place of a timestamp that would break byte-identity."""
    assert mixed_document()["findings_schema_version"] == FINDINGS_SCHEMA_VERSION


def test_the_advice_count_equals_the_number_of_entries() -> None:
    """It must equal findings.json's finding_count, so it counts entries and nothing else."""
    document = mixed_document()
    assert document["advice_count"] == len(document["advice"]) == 3


def test_status_counts_holds_all_three_keys_when_all_three_occurred() -> None:
    """One of each, counted separately rather than rolled into a total."""
    assert mixed_document()["status_counts"] == {WRITTEN: 1, REJECTED: 1, UNAVAILABLE: 1}


def test_status_counts_holds_all_three_keys_when_two_are_zero() -> None:
    """A zero is written out, so a reader never subtracts to find one."""
    document = remediation_document([written_entry(FIRST), written_entry(SECOND)])
    assert document["status_counts"] == {WRITTEN: 2, REJECTED: 0, UNAVAILABLE: 0}


def test_status_counts_holds_all_three_keys_with_no_advice_at_all() -> None:
    """An app with no findings still produces the full shape."""
    document = remediation_document([])
    assert set(document["status_counts"]) == set(ADVICE_STATUSES)
    assert document["advice_count"] == 0


def test_entries_are_sorted_by_finding_id() -> None:
    """Two runs walking the findings in different orders must write the same file."""
    document = remediation_document([unavailable_entry(THIRD), written_entry(FIRST),
                                     rejected_entry(SECOND, NAMES_APP_IDENTIFIER)])
    assert [entry["finding_id"] for entry in document["advice"]] == [FIRST, SECOND, THIRD]


def test_two_entries_for_one_finding_are_refused() -> None:
    """The finding id is the join key into findings.json, so it must be unique."""
    with pytest.raises(ValueError, match="share a finding_id"):
        remediation_document([written_entry(FIRST), unavailable_entry(FIRST)])


def test_the_provenance_block_is_carried_through_unchanged() -> None:
    """The same shape findings.json uses, so two files cannot grow two shapes for one fact."""
    run = used_run()
    assert remediation_document([written_entry(FIRST)], run)["model_run"] == run


def test_the_provenance_block_records_an_unreachable_server() -> None:
    """A document-level `unavailable` is how "the server was down" stays visible."""
    document = remediation_document([unavailable_entry(FIRST)], unavailable_run())
    assert document["model_run"]["status"] == "unavailable"
    assert document["model_run"]["model_identifier"] is None


def test_the_document_carries_no_ranking() -> None:
    """Ranking is a findings-document idea; a second copy here would be a second answer."""
    assert "ranking" not in mixed_document()["model_run"]


def test_the_document_has_no_classification_field() -> None:
    """Re-classifying is structurally unrepresentable, not merely checked for."""
    entry = mixed_document()["advice"][0]
    assert "owasp_id" not in entry
    assert "severity" not in entry


def test_the_serialised_form_is_sorted_indented_json_ending_in_a_newline() -> None:
    """The on-disk form is fixed, so a diff between runs shows content and not formatting."""
    text = remediation_to_json(mixed_document())
    assert text.endswith("\n")
    assert json.loads(text) == mixed_document()
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"


def test_the_builder_does_not_mutate_the_list_it_was_given() -> None:
    """Sorting happens on a copy, so a caller's order survives the call."""
    entries = [unavailable_entry(THIRD), written_entry(FIRST)]
    build_remediation_document(entries, used_run(), no_knowledge(), FINDINGS_SCHEMA_VERSION)
    assert [entry["finding_id"] for entry in entries] == [THIRD, FIRST]
