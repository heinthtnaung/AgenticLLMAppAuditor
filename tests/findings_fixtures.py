"""Shared Phase 3 test data: one valid finding, one confirmed probe, one document.

Several test files build the same small records. Spelling them once here keeps
a change to the record shape a change in one place, and keeps each test about
the rule it checks rather than about its setup. The corpus helper at the bottom
builds a real app's findings from its real surfaces and its recorded SBOM, so
no test needs Syft installed.
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
from artifacts.mapping import build_mapping
from checks.run_checks import build_findings, run_static_checks
from conftest import app_path, require_corpus
from parsing.extractor import extract_repo
from parsing.repo_loader import local_module_names

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


def corpus_inputs(app: str, sbom: dict) -> tuple[str, list, dict]:
    """Return one corpus app's path, its real surfaces and its mapping to the recorded SBOM."""
    require_corpus(app)
    path = str(app_path(app))
    surfaces = extract_repo(path).surfaces
    return path, surfaces, build_mapping(surfaces, sbom, local_module_names(path))


def corpus_findings(app: str, sbom: dict) -> dict:
    """Build one corpus app's whole findings document, every check included."""
    return build_findings(*corpus_inputs(app, sbom))


def corpus_findings_without_mapping(app: str) -> dict:
    """Build one corpus app's findings with no mapping at all.

    For a fixture whose dependencies this tool cannot read: no manifest means no
    bill of materials, so the supply-chain check has nothing to examine and must
    be absent from `checks_run` rather than present and silent.
    """
    require_corpus(app)
    path = str(app_path(app))
    return build_findings(path, extract_repo(path).surfaces, None)


def corpus_static_check_findings(app: str, sbom: dict) -> list[Finding]:
    """Run only the two checks Tasks 3.2 and 3.3 built, so a later check cannot mask them."""
    _, surfaces, mapping = corpus_inputs(app, sbom)
    return run_static_checks(surfaces, mapping)
