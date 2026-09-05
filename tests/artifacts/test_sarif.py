"""The SARIF document: its driver, its rules, and what it says about itself.

One half of the conversion. The per-result mapping -- ruleId, message,
location, property bag -- is next door in test_sarif_results.py, and the
byte-identity claims are in test_sarif_determinism.py.
"""

from artifacts.finding import SCHEMA_VERSION
from artifacts.sarif import (
    DRIVER_NAME,
    FINDINGS_ARTIFACT,
    RESULT_LEVEL,
    SARIF_SCHEMA,
    SARIF_VERSION,
    to_sarif,
)
from checks.permissions import CHECK_NAME as PERMISSION_RULE
from checks.permissions import OWASP_ID as PERMISSION_OWASP
from checks.permissions import TITLE as PERMISSION_TITLE
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_RULE
from checks.taint import CHECK_NAME as TAINT_RULE
from checks.taint import OWASP_ID as TAINT_OWASP
from findings_fixtures import build_document, static_finding
from sarif_fixtures import component_finding, sarif_of, taint_finding

# A second surface, so one rule can fire twice without two findings sharing an id.
OTHER_SURFACE_ID = "app/agent.py:12:TOOL_CALL:Other"


def test_the_document_names_the_sarif_schema_and_version() -> None:
    """A consumer picks its parser from these two, so both are pinned."""
    document = to_sarif(build_document([static_finding()]))
    assert document["$schema"] == SARIF_SCHEMA
    assert document["version"] == SARIF_VERSION == "2.1.0"


def test_the_driver_is_named_but_carries_no_version() -> None:
    """This project has no version number, so the optional key is absent, not empty."""
    driver = sarif_of(static_finding())["tool"]["driver"]
    assert driver["name"] == DRIVER_NAME
    assert "version" not in driver


def test_every_result_carries_the_constant_warning_level() -> None:
    """No severity is reported anywhere, so a varying level would be an invented claim."""
    run = sarif_of(static_finding(), taint_finding(), component_finding())
    assert [result["level"] for result in run["results"]] == [RESULT_LEVEL] * 3
    assert RESULT_LEVEL == "warning"


def test_the_rules_list_only_the_rules_that_fired() -> None:
    """An unfired rule would read as 'ran and found nothing', which SARIF cannot say."""
    rules = sarif_of(static_finding(), taint_finding())["tool"]["driver"]["rules"]
    assert [rule["id"] for rule in rules] == sorted((PERMISSION_RULE, TAINT_RULE))
    assert SUPPLY_CHAIN_RULE not in str(rules)


def test_one_rule_is_described_once_however_often_it_fires() -> None:
    """Two findings of the same rule are two results and one rule entry."""
    run = sarif_of(static_finding(),
                   static_finding(surface_name="Other", surface_id=OTHER_SURFACE_ID))
    assert len(run["results"]) == 2
    assert [rule["id"] for rule in run["tool"]["driver"]["rules"]] == [PERMISSION_RULE]


def test_each_rule_carries_its_title_and_its_owasp_id() -> None:
    """The rule is where a reader looks up what the id means."""
    rules = sarif_of(static_finding(), taint_finding())["tool"]["driver"]["rules"]
    described = {rule["id"]: rule for rule in rules}
    assert described[PERMISSION_RULE]["shortDescription"]["text"] == PERMISSION_TITLE
    assert described[PERMISSION_RULE]["properties"]["owasp_id"] == PERMISSION_OWASP
    assert described[TAINT_RULE]["properties"]["owasp_id"] == TAINT_OWASP


def test_the_run_properties_name_the_contract_this_copy_came_from() -> None:
    """The findings schema version stands in for a timestamp: what invalidates the file."""
    document = build_document([static_finding()])
    properties = to_sarif(document)["runs"][0]["properties"]
    assert properties["findings_schema_version"] == document["schema_version"] == SCHEMA_VERSION


def test_the_run_properties_name_the_file_that_holds_the_coverage() -> None:
    """SARIF cannot say what was not examined, so it names the file that can."""
    assert sarif_of(static_finding())["properties"]["findings_artifact"] == FINDINGS_ARTIFACT
    assert FINDINGS_ARTIFACT == "findings.json"


def test_there_is_one_result_per_finding_in_the_document_order() -> None:
    """The copy neither reorders nor drops: the sorted document order carries through."""
    document = build_document([static_finding(), taint_finding(), component_finding()])
    results = to_sarif(document)["runs"][0]["results"]
    assert len(results) == document["finding_count"]
    assert [r["properties"]["finding_id"] for r in results] == [
        f["finding_id"] for f in document["findings"]]


def test_a_document_with_no_findings_yields_an_empty_run() -> None:
    """A clean app is a valid result: one run, no results, no rules, and no error."""
    run = to_sarif(build_document([], surfaces_considered=0))["runs"][0]
    assert run["results"] == []
    assert run["tool"]["driver"]["rules"] == []
