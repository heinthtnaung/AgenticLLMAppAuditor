"""An advisory finding in SARIF: addressable by its CVE, with nothing lost.

The one deliberate departure in the derived copy: `ruleId` becomes the advisory
id, because the standard VEX filter joins on ruleId being a CVE-/GHSA-scheme
identifier and nothing else. The check name must survive the move, so it stays
in the property bag -- and every non-advisory finding converts exactly as it
did before the departure existed.
"""

from advisory_fixtures import (
    ADVISORY_ID,
    CVSS_SOURCE,
    CVSS_VECTOR,
    FIXED_VERSION,
    advisory_finding,
)
from artifacts.sarif import RESULT_LEVEL
from checks.known_advisory import CHECK_NAME, OWASP_ID, TITLE
from findings_fixtures import static_finding
from sarif_fixtures import sarif_of

SECOND_ADVISORY = "GHSA-xxxx-yyyy-zzzz"
OTHER_SURFACE_ID = "app/agent.py:30:TOOL_CALL:PythonREPLTool"


def second_surface_finding(advisory_id: str):
    """The same advisory reached from a second surface, so ids stay unique."""
    return advisory_finding(advisory_id=advisory_id, surface_id=OTHER_SURFACE_ID,
                            surface_name="PythonREPLTool", line=30)


def advisory_result(*findings) -> dict:
    """Convert the given findings and return the first advisory result."""
    run = sarif_of(*findings)
    return next(r for r in run["results"] if r["ruleId"] == ADVISORY_ID)


def test_the_advisory_id_is_the_rule_id_of_the_result() -> None:
    """What makes the result addressable by a maintainer's VEX statement."""
    assert advisory_result(advisory_finding())["ruleId"] == ADVISORY_ID


def test_the_check_name_survives_in_the_property_bag() -> None:
    """ruleId became the CVE, so the bag is where the check's name must not be lost."""
    assert advisory_result(advisory_finding())["properties"]["rule_id"] == CHECK_NAME


def test_the_result_carries_every_advisory_field_including_severity() -> None:
    """The id, the fix, the quoted vector, its source and the severity word travel."""
    properties = advisory_result(advisory_finding())["properties"]
    assert properties["advisory_id"] == ADVISORY_ID
    assert properties["advisory_fixed_version"] == FIXED_VERSION
    assert properties["advisory_cvss_vector"] == CVSS_VECTOR
    assert properties["advisory_cvss_source"] == CVSS_SOURCE
    assert properties["advisory_severity"] == "HIGH"


def test_a_null_severity_is_absent_from_the_property_bag() -> None:
    """The bag omits null fields, so an unrated advisory carries no severity key."""
    finding = advisory_finding(advisory_severity=None)
    assert "advisory_severity" not in advisory_result(finding)["properties"]


def test_an_advisory_result_keeps_the_constant_level() -> None:
    """No severity judgement sneaks in through the CVE: the level stays `warning`."""
    assert advisory_result(advisory_finding())["level"] == RESULT_LEVEL


def test_the_rules_list_holds_one_rule_per_advisory_id() -> None:
    """Two CVEs are two rules; the same CVE on two surfaces is still one rule."""
    run = sarif_of(advisory_finding(), second_surface_finding(ADVISORY_ID),
                   second_surface_finding(SECOND_ADVISORY))
    rules = run["tool"]["driver"]["rules"]
    assert [rule["id"] for rule in rules] == sorted([ADVISORY_ID, SECOND_ADVISORY])


def test_each_advisory_rule_carries_the_checks_constant_title_and_risk() -> None:
    """The rule describes the check that fired, whatever CVE names the rule."""
    for rule in sarif_of(advisory_finding())["tool"]["driver"]["rules"]:
        assert rule["shortDescription"]["text"] == TITLE
        assert rule["properties"]["owasp_id"] == OWASP_ID


def test_a_non_advisory_result_is_unchanged_by_an_advisory_beside_it() -> None:
    """The departure is scoped: every other finding converts byte-for-byte as before."""
    alone = sarif_of(static_finding())["results"][0]
    run = sarif_of(static_finding(), advisory_finding())
    beside = next(r for r in run["results"] if r["ruleId"] != ADVISORY_ID)
    assert beside == alone
    assert beside["ruleId"] == static_finding().rule_id
    assert not any(key.startswith("advisory_") for key in beside["properties"])
