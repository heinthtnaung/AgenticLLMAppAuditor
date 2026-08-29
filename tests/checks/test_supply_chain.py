"""LLM03: a package a surface uses that no dependency manifest declares.

The check reads `mapping.json`, so these tests feed it mapping entries and the
surface fields a finding copies. What matters is which of the five mapping
reasons reaches a finding: `used_but_undeclared` is one, and `unresolved` --
"we could not tell which package" -- deliberately is not.
"""

import pytest

from artifacts.finding import STATIC
from artifacts.mapping import (
    FIRST_PARTY,
    MAPPING_REASONS,
    STDLIB,
    THIRD_PARTY,
    UNRESOLVED,
    USED_BUT_UNDECLARED,
)
from artifacts.surface import DATA_SOURCE
from checks.supply_chain import (
    CHECK_NAME,
    OWASP_ID,
    find_undeclared_dependencies,
    unresolved_component_count,
)

SURFACE_ID = "utils.py:75:DATA_SOURCE:yaml.load"
COMPONENT = "pyyaml"

SURFACE_FIELDS = {
    SURFACE_ID: {
        "surface_kind": DATA_SOURCE, "surface_name": "yaml.load",
        "file": "utils.py", "line": 75,
    },
}


def mapping_entry(reason: str = USED_BUT_UNDECLARED,
                  component_name: str | None = COMPONENT,
                  surface_id: str = SURFACE_ID) -> dict:
    """Build one mapping.json entry, with only the fields this check reads."""
    return {"surface_id": surface_id, "reason": reason, "component_name": component_name}


def mapping_document(*entries: dict) -> dict:
    """Wrap entries in the shape build_mapping produces."""
    return {"entries": list(entries)}


def reason_counts(counts: dict[str, int]) -> dict:
    """Wrap reason counts in the shape build_mapping produces, zeros included."""
    return {"reason_counts": {reason: 0 for reason in MAPPING_REASONS} | counts}


def test_an_undeclared_package_is_reported() -> None:
    """The supported case: a surface reached a package no manifest declares."""
    findings = find_undeclared_dependencies(mapping_document(mapping_entry()), SURFACE_FIELDS)
    assert len(findings) == 1
    assert (findings[0].owasp_id, findings[0].rule_id) == (OWASP_ID, CHECK_NAME)


def test_the_finding_cites_the_component_and_the_mapping_reason() -> None:
    """Both halves of the evidence travel with it, so nobody re-derives the join."""
    finding = find_undeclared_dependencies(mapping_document(mapping_entry()), SURFACE_FIELDS)[0]
    assert finding.component_name == COMPONENT
    assert finding.mapping_reason == USED_BUT_UNDECLARED


def test_the_finding_copies_the_surface_it_came_from() -> None:
    """Phase 4 joins on file and line, so both are copied rather than parsed out of the id."""
    finding = find_undeclared_dependencies(mapping_document(mapping_entry()), SURFACE_FIELDS)[0]
    assert finding.surface_id == SURFACE_ID
    assert (finding.file, finding.line) == ("utils.py", 75)
    assert (finding.surface_kind, finding.surface_name) == (DATA_SOURCE, "yaml.load")


def test_an_undeclared_package_carries_no_purl() -> None:
    """It has no SBOM component, so there is no version-keyed handle to record."""
    finding = find_undeclared_dependencies(mapping_document(mapping_entry()), SURFACE_FIELDS)[0]
    assert finding.purl is None
    assert finding.detection == STATIC


@pytest.mark.parametrize("reason", (THIRD_PARTY, STDLIB, FIRST_PARTY, UNRESOLVED))
def test_no_other_mapping_reason_is_a_finding(reason: str) -> None:
    """`unresolved` is the load-bearing one: not knowing the package is not a finding."""
    document = mapping_document(mapping_entry(reason=reason))
    assert find_undeclared_dependencies(document, SURFACE_FIELDS) == []


def test_an_entry_naming_no_component_is_not_a_finding() -> None:
    """Without a package name there is nothing anyone could go and declare."""
    document = mapping_document(mapping_entry(component_name=None))
    assert find_undeclared_dependencies(document, SURFACE_FIELDS) == []


def test_an_entry_whose_surface_is_unknown_is_skipped() -> None:
    """A finding must copy its surface, so one that cannot be found is not reported."""
    document = mapping_document(mapping_entry(surface_id="gone.py:1:DATA_SOURCE:x"))
    assert find_undeclared_dependencies(document, SURFACE_FIELDS) == []


def test_a_mapping_with_no_entries_produces_nothing() -> None:
    """An app whose surfaces all mapped cleanly is a valid, empty result."""
    assert find_undeclared_dependencies(mapping_document(), SURFACE_FIELDS) == []


def test_two_surfaces_on_one_package_are_two_findings() -> None:
    """Each is its own place the undeclared package is reached, with its own id."""
    other_id = "utils.py:80:DATA_SOURCE:yaml.load"
    fields = {**SURFACE_FIELDS, other_id: {**SURFACE_FIELDS[SURFACE_ID], "line": 80}}
    document = mapping_document(mapping_entry(), mapping_entry(surface_id=other_id))
    findings = find_undeclared_dependencies(document, fields)
    assert len({finding.id for finding in findings}) == 2


# --- The count of surfaces owning no component -----------------------------

def test_no_mapping_at_all_counts_nothing_rather_than_none_unresolved() -> None:
    """Null says there was no bill of materials; 0 would claim a reach the check never had."""
    assert unresolved_component_count(None) is None


def test_only_the_unresolved_reason_is_counted() -> None:
    """`stdlib` and `first_party` are answers, and `used_but_undeclared` is already a finding."""
    document = reason_counts(
        {UNRESOLVED: 2, STDLIB: 3, FIRST_PARTY: 1, USED_BUT_UNDECLARED: 1})
    assert unresolved_component_count(document) == 2


def test_a_mapping_that_resolved_every_surface_counts_zero() -> None:
    """A mapping existed and left no gap, which is not the same as no mapping."""
    assert unresolved_component_count(reason_counts({THIRD_PARTY: 4})) == 0


def test_a_mapping_without_reason_counts_is_refused() -> None:
    """A hand-built dict is not a mapping.json, and guessing 0 from it would be a false claim."""
    with pytest.raises(ValueError, match="no reason_counts"):
        unresolved_component_count({"entries": []})
