"""Shared Phase 3 test data: one valid finding, one confirmed probe, one document.

Several test files build the same small records. Spelling them once here keeps
a change to the record shape a change in one place, and keeps each test about
the rule it checks rather than about its setup.

Everything here is built in memory. The helpers that assembled a pinned app's
findings from its real surfaces went with the corpus; a test that wants a whole
document over real source writes the source itself.
"""

from artifacts.finding import (
    CONFIRMED,
    PROBE,
    STATIC,
    SURFACE_SUBJECT,
    Finding,
    Probe,
)
from artifacts.findings_document import (
    MODEL_DISABLED,
    build_findings_document,
    coverage,
    model_run,
)

# One surface, copied whole as the schema requires: a finding carries its
# kind, name, file and line so Phase 4 never has to parse the id.
SURFACE_ID = "app/agent.py:12:TOOL_CALL:ShellTool"
SURFACE_FIELDS = {
    "surface_id": SURFACE_ID,
    "surface_kind": "TOOL_CALL",
    "surface_name": "ShellTool",
    "file": "app/agent.py",
    "line": 12,
}

RULE_ID = "high_privilege_tool"
TITLE = "Agent tool grants shell, interpreter or network access"
OWASP_ID = "LLM06"

PROBE_NAME = "static_permission_check"


def static_finding(**overrides) -> Finding:
    """Build a valid static finding citing one surface; any field can be overridden."""
    fields = {
        "owasp_id": OWASP_ID, "rule_id": RULE_ID, "title": TITLE,
        "detection": STATIC, **SURFACE_FIELDS, **overrides,
    }
    return Finding(**fields)


def confirmed_probe(subject_id: str = SURFACE_ID) -> Probe:
    """Build a probe that ran and confirmed, which a probe finding may cite."""
    return Probe(PROBE_NAME, SURFACE_SUBJECT, subject_id, CONFIRMED, "the tool holds a shell")


def probe_finding(probe: Probe, **overrides) -> Finding:
    """Build a finding reached by a probe, citing that probe."""
    return static_finding(detection=PROBE, probe_id=probe.id, **overrides)


def build_document(findings, probes=(), run=None, surfaces_considered: int = 1) -> dict:
    """Assemble a findings document with the defaults every test but one shares."""
    return build_findings_document(
        list(findings), list(probes),
        coverage(surfaces_considered, [RULE_ID]),
        run if run is not None else model_run(MODEL_DISABLED),
    )
