"""Shared Phase 4 test data: one grading key, one findings document, one scan.

The scorer takes three documents and every test needs all three, so they are
built once here from the real constructors -- `Finding`, `build_findings_
document`, `surfaces_to_json` -- rather than hand-written as dicts. A test that
invents the shape of its input can pass against a schema nobody produces.

The defaults are the boring case: a key that is complete, verified and
hand-checked, one produced finding that answers its one entry. Each test
overrides the single field it is about.
"""

import json

from collections.abc import Sequence

from artifacts.finding import INCONCLUSIVE, SURFACE_SUBJECT, Finding, Probe
from artifacts.findings_document import (
    ADVISORY_NOT_INGESTED,
    ADVISORY_SNAPSHOT,
    MODEL_DISABLED,
    build_findings_document,
    coverage,
    model_run,
)
from artifacts.skipped_file import UNPARSEABLE_SYNTAX, SkippedFile
from artifacts.surface import Surface, surfaces_to_json
from findings_fixtures import OWASP_ID, RULE_ID, SURFACE_FIELDS, SURFACE_ID, static_finding
from parsing.languages import PYTHON

APP = "tiny-app"
COMMIT = "c0cf9a14adad76e9d6a53c41741f625334bd9971"
KEY_ID = "TINY-01"

# The surface the fixture finding cites, spelled as the key would record it.
FILE = SURFACE_FIELDS["file"]
LINE = SURFACE_FIELDS["line"]
SURFACE_KIND = SURFACE_FIELDS["surface_kind"]
SURFACE_NAME = SURFACE_FIELDS["surface_name"]

# A second location, for a finding the key does not list.
UNRELATED_FILE = "app/web.py"
UNRELATED_SURFACE_ID = f"{UNRELATED_FILE}:5:DATA_SOURCE:request.body"

# A probe that gave up, so a miss can be attributed to an unresolved trace.
PROBE_NAME = "reachability_trace"
PROBE_REASON = "trace_left_static_analysis"


def key_entry(**overrides) -> dict:
    """One grading-key entry, answered by `static_finding()` unless overridden."""
    entry = {
        "id": KEY_ID, "owasp_id": OWASP_ID, "file": FILE, "line": LINE, "line_end": None,
        "llm_surface": SURFACE_KIND, "surface_name": SURFACE_NAME, "detection": "either",
    }
    return {**entry, **overrides}


def grading_key(entries: list[dict], **overrides) -> dict:
    """A whole key: complete, verified and hand-reviewed, so a test relaxes one flag at a time."""
    key = {
        "app": APP, "schema_version": 2, "findings": list(entries),
        "findings_complete": True, "expected_surfaces_complete": True,
        "source": "manual_review", "verified": True, "verified_by": "a person",
        "verified_date": "2026-01-01", "upstream_commit": COMMIT,
    }
    return {**key, **overrides}


def findings_document(findings: Sequence = (), probes: Sequence = (),
                      risk_classes: Sequence[str] = (OWASP_ID,), run: dict | None = None,
                      advisory: str = ADVISORY_NOT_INGESTED,
                      unresolved_components: int | None = None) -> dict:
    """A findings document built the way the tool builds it, so the scorer reads real fields."""
    from cli_helpers import STUB_ADVISORY_PIN
    pin = STUB_ADVISORY_PIN if advisory == ADVISORY_SNAPSHOT else {}
    return build_findings_document(
        list(findings), list(probes),
        coverage(1, [RULE_ID], advisory, risk_classes_checked=list(risk_classes),
                 unresolved_component_count=unresolved_components, **pin),
        run if run is not None else model_run(MODEL_DISABLED),
    )


def surfaces_document(files=(FILE,), skipped=()) -> dict:
    """The scan record a miss is attributed against: what was seen, and what was not read."""
    surfaces = [
        Surface(kind=SURFACE_KIND, name=SURFACE_NAME, file=name, line=LINE,
                language=PYTHON, detail="", module="")
        for name in files
    ]
    skips = [SkippedFile(file=name, reason=UNPARSEABLE_SYNTAX) for name in skipped]
    return json.loads(surfaces_to_json(surfaces, skips))


def unrelated_finding() -> Finding:
    """A produced finding no key entry answers, so precision has something to count."""
    return static_finding(
        owasp_id="LLM01", rule_id="untrusted_input",
        title="Untrusted input reaches the agent unfiltered",
        surface_id=UNRELATED_SURFACE_ID, surface_kind="DATA_SOURCE",
        surface_name="request.body", file=UNRELATED_FILE, line=5)


def unresolved_probe(subject_id: str = SURFACE_ID) -> Probe:
    """A probe that reached no conclusion, which is a miss reason of its own."""
    return Probe(PROBE_NAME, SURFACE_SUBJECT, subject_id, INCONCLUSIVE,
                 "the trace left static analysis", PROBE_REASON)


def every_value(node) -> list:
    """Return every scalar in a nested document, so a whole file can be asserted over.

    Shared because the no-float rule is checked over a whole document rather
    than field by field: a float anywhere in it is the thing being refused.
    """
    if isinstance(node, dict):
        return [value for child in node.values() for value in every_value(child)]
    if isinstance(node, list):
        return [value for child in node for value in every_value(child)]
    return [node]


def answered_key() -> tuple[dict, dict, dict]:
    """The default trio: one key entry, one finding that answers it, one clean scan."""
    return (grading_key([key_entry()]),
            findings_document([static_finding()]),
            surfaces_document())
