"""LLM03: a known advisory in a component an LLM surface actually reaches.

The check joins two documents -- the mapping's reached components and the
advisory index -- so these tests feed it both by hand. The load-bearing shape
is one finding per (surface, component, advisory), anchored on the surface so
Phase 4 has a file and a line to score.
"""

from advisory_fixtures import ADVISORY_PURL, advisory_record
from artifacts.surface import TOOL_CALL, Surface
from checks.known_advisory import (
    CHECK_NAME,
    OWASP_ID,
    TITLE,
    find_known_advisories,
    unreached_component_count,
    unreached_components,
)
from checks.supply_chain import surface_fields
from parsing.languages import PYTHON

SURFACE = Surface(TOOL_CALL, "ShellTool", "app/agent.py", 12, PYTHON,
                  "tool", "langchain.tools")
OTHER_SURFACE = Surface(TOOL_CALL, "PythonREPLTool", "app/agent.py", 30, PYTHON,
                        "tool", "langchain.tools")
FIELDS = surface_fields([SURFACE, OTHER_SURFACE])

THREE_ADVISORIES = [advisory_record("CVE-2024-0001"), advisory_record("CVE-2024-0002"),
                    advisory_record("GHSA-xxxx-yyyy-zzzz")]

UNREACHED_PURL = "pkg:pypi/requests@2.31.0"
SECOND_UNREACHED_PURL = "pkg:pypi/urllib3@2.0.7"


def mapping_entry(surface: Surface = SURFACE, purl: str | None = ADVISORY_PURL) -> dict:
    """One mapping.json entry, with only the fields this check reads."""
    return {"surface_id": surface.id, "purl": purl,
            "component_name": "langchain", "reason": "third_party"}


def mapping_document(*entries: dict) -> dict:
    """Wrap entries in the shape build_mapping produces."""
    return {"entries": list(entries)}


def test_no_mapping_means_no_findings() -> None:
    """Without a mapping there is no reach to join against, so nothing is claimed."""
    assert find_known_advisories(None, {ADVISORY_PURL: THREE_ADVISORIES}, FIELDS) == []


def test_no_advisory_data_means_no_findings() -> None:
    """Without advisories there is nothing known to be wrong, so nothing is claimed."""
    assert find_known_advisories(mapping_document(mapping_entry()), None, FIELDS) == []


def test_three_advisories_on_one_reached_component_are_three_findings() -> None:
    """The plan's checklist item: one finding per (surface, component, advisory)."""
    found = find_known_advisories(mapping_document(mapping_entry()),
                                  {ADVISORY_PURL: THREE_ADVISORIES}, FIELDS)
    assert len(found) == 3
    assert len({finding.id for finding in found}) == 3


def test_each_finding_cites_its_own_advisory() -> None:
    """Three findings on one surface differ only in the advisory each one quotes."""
    found = find_known_advisories(mapping_document(mapping_entry()),
                                  {ADVISORY_PURL: THREE_ADVISORIES}, FIELDS)
    assert sorted(f.advisory_id for f in found) == sorted(
        record["advisory_id"] for record in THREE_ADVISORIES)


def test_two_surfaces_reaching_one_component_are_two_findings_per_advisory() -> None:
    """Each surface is its own place the vulnerable component is reached."""
    document = mapping_document(mapping_entry(), mapping_entry(surface=OTHER_SURFACE))
    found = find_known_advisories(document, {ADVISORY_PURL: THREE_ADVISORIES}, FIELDS)
    assert len(found) == 6
    assert {f.surface_id for f in found} == {SURFACE.id, OTHER_SURFACE.id}


def test_an_entry_with_no_purl_is_skipped() -> None:
    """No purl means the join never happened, so there is no reach to report."""
    document = mapping_document(mapping_entry(purl=None))
    assert find_known_advisories(document, {ADVISORY_PURL: THREE_ADVISORIES}, FIELDS) == []


def test_the_finding_is_anchored_on_the_surface_it_copied() -> None:
    """File, line, kind and name come from the surface, so a grading key can score it."""
    finding = find_known_advisories(mapping_document(mapping_entry()),
                                    {ADVISORY_PURL: [advisory_record()]}, FIELDS)[0]
    assert (finding.file, finding.line) == ("app/agent.py", 12)
    assert (finding.surface_kind, finding.surface_name) == (TOOL_CALL, "ShellTool")
    assert finding.surface_id == SURFACE.id


def test_the_finding_carries_the_rule_the_risk_and_the_join_evidence() -> None:
    """The claim and everything a reader needs to check it themselves."""
    finding = find_known_advisories(mapping_document(mapping_entry()),
                                    {ADVISORY_PURL: [advisory_record()]}, FIELDS)[0]
    assert (finding.owasp_id, finding.rule_id, finding.title) == (OWASP_ID, CHECK_NAME, TITLE)
    assert (finding.purl, finding.component_name) == (ADVISORY_PURL, "langchain")
    assert finding.mapping_reason == "third_party"


# --- The count of advisory-carrying components nothing reaches ---------------

def test_no_mapping_counts_nothing_rather_than_zero() -> None:
    """Null says there was no reach to measure; 0 would claim every advisory was reached."""
    assert unreached_component_count(None, {ADVISORY_PURL: THREE_ADVISORIES}) is None


def test_no_advisory_data_counts_nothing_rather_than_zero() -> None:
    """Null says nothing was known to be wrong; 0 would claim a scan that never ran."""
    assert unreached_component_count(mapping_document(mapping_entry()), None) is None


def test_every_advisory_component_reached_counts_zero() -> None:
    """A scan ran and every dangerous component is reached: a real, zero-gap answer."""
    assert unreached_component_count(mapping_document(mapping_entry()),
                                     {ADVISORY_PURL: THREE_ADVISORIES}) == 0


def test_distinct_unreached_purls_are_counted_once_each() -> None:
    """Components, not advisories: two purls nothing reaches count 2, however many CVEs each."""
    advisories = {ADVISORY_PURL: THREE_ADVISORIES,
                  UNREACHED_PURL: [advisory_record("CVE-2024-1111"),
                                   advisory_record("CVE-2024-2222")],
                  SECOND_UNREACHED_PURL: [advisory_record("CVE-2024-3333")]}
    assert unreached_component_count(mapping_document(mapping_entry()), advisories) == 2


def test_no_data_itemizes_nothing_rather_than_an_empty_list() -> None:
    """Null, not [], because [] would claim a scan ran and found no unreached component."""
    assert unreached_components(mapping_document(mapping_entry()), None) is None
    assert unreached_components(None, {ADVISORY_PURL: THREE_ADVISORIES}) is None


def test_unreached_components_are_itemized_sorted_with_their_advisory_ids() -> None:
    """The list behind the count: each unreached purl with its ids, both orders stable."""
    advisories = {ADVISORY_PURL: THREE_ADVISORIES,
                  SECOND_UNREACHED_PURL: [advisory_record("CVE-2024-3333")],
                  UNREACHED_PURL: [advisory_record("CVE-2024-2222"),
                                   advisory_record("CVE-2024-1111")]}
    items = unreached_components(mapping_document(mapping_entry()), advisories)
    assert [item["purl"] for item in items] == sorted([UNREACHED_PURL, SECOND_UNREACHED_PURL])
    by_purl = {item["purl"]: [a["id"] for a in item["advisories"]] for item in items}
    assert by_purl[UNREACHED_PURL] == ["CVE-2024-1111", "CVE-2024-2222"]
    assert ADVISORY_PURL not in by_purl, "a reached component is not in the unreached list"


def test_the_count_is_exactly_the_length_of_the_list() -> None:
    """They are one fact at two grains, so the count can never disagree with the list."""
    advisories = {ADVISORY_PURL: THREE_ADVISORIES,
                  UNREACHED_PURL: [advisory_record("CVE-2024-2222")],
                  SECOND_UNREACHED_PURL: [advisory_record("CVE-2024-3333")]}
    doc = mapping_document(mapping_entry())
    assert unreached_component_count(doc, advisories) == len(unreached_components(doc, advisories))
