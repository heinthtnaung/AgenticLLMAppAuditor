"""One finding becomes one SARIF result: where each field of it lands.

The other half of the conversion, split from test_sarif.py, which covers the
document the results sit in. A field mapped to the wrong place here is a silent
lie told to a stranger's tool, so each one is asserted by name rather than by
comparing the whole result to a blob.
"""

from artifacts.finding import PROBE, STATIC
from dataclasses import fields

from artifacts.finding import Finding
from artifacts.findings_document import MODEL_AUTHORED_FINDING_FIELD
from artifacts.sarif import RESULT_PROPERTIES
from checks.permissions import CHECK_NAME as PERMISSION_RULE
from checks.permissions import TITLE as PERMISSION_TITLE
from findings_fixtures import confirmed_probe, probe_finding, static_finding
from sarif_fixtures import (
    COMPONENT_NAME,
    COMPONENT_PURL,
    MAPPING_REASON,
    component_finding,
    sarif_of,
    taint_finding,
)

# The fixture surface, and a file with no line the conversion must not round up.
SURFACE_FILE = "app/agent.py"
SURFACE_LINE = 12
UNLOCATED_FILE = "utils.py"


def test_the_result_takes_its_rule_id_and_its_message_from_the_finding() -> None:
    """`ruleId` from rule_id, `message.text` from the title the rule fixed."""
    result = sarif_of(static_finding())["results"][0]
    assert result["ruleId"] == PERMISSION_RULE
    assert result["message"]["text"] == PERMISSION_TITLE


def test_no_result_repeats_the_owasp_id_the_rule_holds() -> None:
    """One fact, one home: it is constant on the rule, so the result must not carry it."""
    for result in sarif_of(static_finding(), taint_finding())["results"]:
        assert "owasp_id" not in result
        assert "owasp_id" not in result["properties"]


def test_the_location_carries_the_file_and_the_line() -> None:
    """Repo-relative uri and startLine: what makes a result openable in an editor."""
    physical = sarif_of(static_finding())["results"][0]["locations"][0]["physicalLocation"]
    assert physical["artifactLocation"]["uri"] == SURFACE_FILE
    assert physical["region"]["startLine"] == SURFACE_LINE


def test_a_finding_with_no_location_gets_an_empty_location_list() -> None:
    """A component finding points at no code, so SARIF is given nothing to point at."""
    assert sarif_of(component_finding())["results"][0]["locations"] == []


def test_a_finding_with_a_file_but_no_line_gets_no_region() -> None:
    """A region would put the finding on a line the analysis never claimed."""
    finding = component_finding(file=UNLOCATED_FILE)
    physical = sarif_of(finding)["results"][0]["locations"][0]["physicalLocation"]
    assert physical["artifactLocation"]["uri"] == UNLOCATED_FILE
    assert "region" not in physical


def test_the_property_bag_carries_the_surface_the_finding_cites() -> None:
    """Copied whole, so a consumer never has to parse a surface id."""
    finding = static_finding()
    properties = sarif_of(finding)["results"][0]["properties"]
    assert properties["finding_id"] == finding.id
    assert properties["surface_id"] == finding.surface_id
    assert properties["surface_kind"] == "TOOL_CALL"
    assert properties["surface_name"] == "ShellTool"
    assert properties["detection"] == STATIC


def test_the_property_bag_carries_the_component_a_supply_chain_finding_cites() -> None:
    """The other evidence shape: purl, component name and why the mapping flagged it."""
    properties = sarif_of(component_finding())["results"][0]["properties"]
    assert properties["purl"] == COMPONENT_PURL
    assert properties["component_name"] == COMPONENT_NAME
    assert properties["mapping_reason"] == MAPPING_REASON


def test_the_property_bag_names_the_probe_a_probe_finding_cites() -> None:
    """A finding reached by a probe carries the probe id and says so in `detection`."""
    probe = confirmed_probe()
    properties = sarif_of(probe_finding(probe), probes=[probe])["results"][0]["properties"]
    assert properties["probe_id"] == probe.id
    assert properties["detection"] == PROBE


def test_an_evidence_field_the_finding_left_null_is_omitted() -> None:
    """Absent, never present-and-null: a null in a property bag reads as a value."""
    properties = sarif_of(static_finding())["results"][0]["properties"]
    assert "purl" not in properties
    assert "component_name" not in properties
    assert "probe_id" not in properties
    assert None not in properties.values()


def test_the_property_bag_holds_nothing_the_contract_did_not_name() -> None:
    """The bag is the named nine, so no field arrives here without a decision."""
    run = sarif_of(static_finding(), component_finding())
    for result in run["results"]:
        assert set(result["properties"]) <= set(RESULT_PROPERTIES)


def test_every_finding_field_is_mapped_or_deliberately_dropped() -> None:
    """A field added to `Finding` must be placed here, not silently lost.

    The bag assertion above is a subset bound, so it would stay green while a
    new field vanished from this artifact -- and `SCHEMAS.md` would go on naming
    a mapping that no longer covers the record. This pins the other direction:
    every field is in the property bag, on the result, on the rule, or dropped
    on purpose.
    """
    on_the_result = {"rule_id", "title", "file", "line"}
    on_the_rule = {"owasp_id"}
    dropped = {MODEL_AUTHORED_FINDING_FIELD}
    placed = set(RESULT_PROPERTIES) | on_the_result | on_the_rule | dropped
    carried = {field.name for field in fields(Finding)} | {"finding_id"}
    assert carried == placed, (
        f"unplaced: {sorted(carried - placed)}; named but not on Finding: "
        f"{sorted(placed - carried)}")
