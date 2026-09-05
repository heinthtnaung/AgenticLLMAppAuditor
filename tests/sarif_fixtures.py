"""Shared SARIF test data: the three finding shapes the conversion has to carry.

Built on `findings_fixtures`, so the record shape is still spelled once. This
module adds only what the SARIF tests need on top of it: the second rule that
makes a rules list worth sorting, and a component finding, which is the shape
with no code location to point at.
"""

from artifacts.sarif import to_sarif
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_RULE
from checks.supply_chain import OWASP_ID as SUPPLY_CHAIN_OWASP
from checks.supply_chain import TITLE as SUPPLY_CHAIN_TITLE
from checks.taint import CHECK_NAME as TAINT_RULE
from checks.taint import OWASP_ID as TAINT_OWASP
from checks.taint import TITLE as TAINT_TITLE
from findings_fixtures import build_document, static_finding

# What a supply-chain finding cites instead of a surface.
COMPONENT_NAME = "pyyaml"
COMPONENT_PURL = "pkg:pypi/pyyaml@6.0.1"
MAPPING_REASON = "used_but_undeclared"


def taint_finding(**overrides):
    """A second rule's finding, so a rules list has more than one entry to sort."""
    return static_finding(rule_id=TAINT_RULE, owasp_id=TAINT_OWASP,
                          title=TAINT_TITLE, **overrides)


def component_finding(file: str | None = None):
    """A supply-chain finding: component evidence, and no surface of its own."""
    return static_finding(
        rule_id=SUPPLY_CHAIN_RULE, owasp_id=SUPPLY_CHAIN_OWASP, title=SUPPLY_CHAIN_TITLE,
        surface_id=None, surface_kind=None, surface_name=None, file=file, line=None,
        component_name=COMPONENT_NAME, purl=COMPONENT_PURL, mapping_reason=MAPPING_REASON)


def sarif_of(*findings, probes=()) -> dict:
    """Convert a document built from the given findings, and return its one run."""
    return to_sarif(build_document(findings, probes))["runs"][0]
