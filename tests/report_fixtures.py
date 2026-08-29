"""Shared test data for the report renderer: its two inputs, and a way to slice its output.

The report is graded on two sections, so its tests are split across two files
and both need the same setup. The slicing helpers matter as much as the
builders: assertions run against one section at a time, so a word appearing in
the wrong section can never satisfy a test.
"""

import json

from artifacts.finding import INCONCLUSIVE, SURFACE_SUBJECT, Probe
from artifacts.findings_document import (
    ADVISORY_NOT_INGESTED,
    MODEL_DISABLED,
    build_findings_document,
    coverage,
    model_run,
)
from artifacts.skipped_file import UNPARSEABLE_SYNTAX, SkippedFile
from artifacts.surface import surfaces_to_json
from checks.taint import LEFT_THE_FILE
from findings_fixtures import RULE_ID, SURFACE_ID

APP = "vulnerable-support-agent"

# The three top-level sections, named once so the slicing helpers and the
# "equal billing" test agree on what a section is.
FINDINGS_HEADING = "## Findings"
NOT_EXAMINED_HEADING = "## What was not examined"
HOW_HEADING = "## How it was audited"

# One file the scan could not parse, so its surfaces are missing from the report.
UNREADABLE = SkippedFile("app/agent.py", UNPARSEABLE_SYNTAX, 3)

# Enough surfaces for a test to hand `coverage` a plural untraceable count and
# still stay inside the one-mapping-entry-per-surface rule it enforces.
SURFACES_CONSIDERED = 3


def surfaces_document(skipped: tuple = ()) -> dict:
    """Build the surfaces artifact the report reads, through its real producer."""
    return json.loads(surfaces_to_json([], list(skipped)))


def document_with_coverage(findings: tuple = (), probes=(), risk_classes: tuple = (),
                           advisory: str = ADVISORY_NOT_INGESTED,
                           unresolved: int | None = None) -> dict:
    """Build a findings document whose coverage block the test controls."""
    return build_findings_document(
        list(findings), list(probes),
        coverage(SURFACES_CONSIDERED, [RULE_ID], advisory, list(risk_classes),
                 unresolved_component_count=unresolved),
        model_run(MODEL_DISABLED),
    )


def unresolved_probe(outcome: str = INCONCLUSIVE) -> Probe:
    """Build a probe that reached no conclusion, which the gap list must name."""
    return Probe("untrusted_input_reaches_model", SURFACE_SUBJECT, SURFACE_ID,
                 outcome, "the value was not bound to a name in this file", LEFT_THE_FILE)


def findings_section(text: str) -> str:
    """Return only the findings part, so a later section cannot satisfy an assertion."""
    return text.split(FINDINGS_HEADING, 1)[1].split(NOT_EXAMINED_HEADING, 1)[0]


def not_examined_section(text: str) -> str:
    """Return only the gap list, so a finding's own text cannot satisfy an assertion."""
    return text.split(NOT_EXAMINED_HEADING, 1)[1].split(HOW_HEADING, 1)[0]
