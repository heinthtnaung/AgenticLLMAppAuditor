"""Shared advisory test data: a hand-built Trivy report and the stub that feeds it in.

Several test files exercise the advisory half of the supply chain: the runner's
pure parts, the check that joins its index to the mapping, and the CLI path
that wires both. The raw-report shape and the Trivy stub are spelled once here,
so no test starts a real subprocess or needs this machine to have Trivy or its
database. `stub_syft` in cli_helpers switches Trivy OFF for the same reason;
`stub_trivy` below is the deliberate opposite, applied after it.

`advisory_document` is here for the same reason: a snapshot's pin and an
advisory finding are two halves of one fact, and the VEX emitter reads both.
"""

import pytest

from artifacts.finding import Finding
from artifacts.findings_document import (
    ADVISORY_SNAPSHOT,
    MODEL_DISABLED,
    build_findings_document,
    coverage,
    model_run,
)
from checks import known_advisory
from deps import trivy_runner
from findings_fixtures import static_finding

# The versioned purl every happy-path test joins on, and the values quoted from
# the hand-built report below. The date differs from STUB_ADVISORY_PIN's on
# purpose: a pin test passing with either would be reading the wrong constant.
ADVISORY_PURL = "pkg:pypi/langchain@0.3.25"
ADVISORY_ID = "CVE-2024-0001"
FIXED_VERSION = "0.3.26"
CVSS_SOURCE = "nvd"
# Trivy's own severity word, spelled once: the fixture writes it into the raw
# report and expects it back out, so two copies could drift apart.
SEVERITY = "HIGH"
CVSS_VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
TRIVY_VERSION = "0.66.0"
DB_UPDATED_AT = "2026-02-01T06:00:00Z"


def trivy_vulnerability(vuln_id: str = ADVISORY_ID, purl: str | None = ADVISORY_PURL,
                        fixed: str = FIXED_VERSION, source: str | None = CVSS_SOURCE,
                        cvss: dict | None = None,
                        severity: str | None = SEVERITY) -> dict:
    """One vulnerability record in the shape Trivy's JSON report writes it.

    `Severity` is Trivy's own field and the runner quotes it, so the fixture
    writes it too; `severity=None` produces the report of a record Trivy rated
    with no word at all.
    """
    record = {
        "VulnerabilityID": vuln_id,
        "PkgIdentifier": {"PURL": purl} if purl else {},
        "FixedVersion": fixed,
        "Severity": severity,
        "SeveritySource": source,
        "CVSS": cvss if cvss is not None else {CVSS_SOURCE: {"V3Vector": CVSS_VECTOR}},
    }
    return record


def trivy_report(*vulnerabilities: dict, version: str = TRIVY_VERSION) -> dict:
    """A whole Trivy report holding the given vulnerability records."""
    return {"Trivy": {"Version": version},
            "Results": [{"Vulnerabilities": list(vulnerabilities)}]}


def advisory_record(advisory_id: str = ADVISORY_ID, fixed: str | None = FIXED_VERSION,
                    vector: str | None = CVSS_VECTOR,
                    source: str | None = CVSS_SOURCE,
                    severity: str | None = SEVERITY) -> dict:
    """One advisory in this project's vocabulary, as advisory_index emits it."""
    return {
        "advisory_id": advisory_id,
        "advisory_fixed_version": fixed,
        "advisory_severity": severity if source else None,
        "advisory_cvss_vector": vector,
        "advisory_cvss_source": source,
    }


def advisory_finding(advisory_id: str = ADVISORY_ID, **overrides) -> Finding:
    """A valid known_advisory finding anchored on the shared fixture surface."""
    fields = {
        "rule_id": known_advisory.CHECK_NAME, "owasp_id": known_advisory.OWASP_ID,
        "title": known_advisory.TITLE, "purl": ADVISORY_PURL,
        "component_name": "langchain", "mapping_reason": "third_party",
        "advisory_id": advisory_id, "advisory_fixed_version": FIXED_VERSION,
        "advisory_severity": SEVERITY,
        "advisory_cvss_vector": CVSS_VECTOR, "advisory_cvss_source": CVSS_SOURCE,
        **overrides,
    }
    return static_finding(**fields)


# The pin a snapshot needs, built from this module's own constants so a test
# reading the wrong date fails rather than passes on cli_helpers' pin.
# The component the JS fixture's tool call reaches, and two real advisories
# against that exact version, as Trivy reported them (transcribed the way
# dependency_fixtures transcribes Syft, so no test needs the binary). The app
# they were recorded against went with the corpus; the transcription stays,
# because it is what lets the advisory path be tested with no binary and no
# tree on disk.
JS_COMPONENT_PURL = "pkg:npm/%40langchain/community@0.3.3"
JS_SURFACE_NOTE = "Reached by TavilySearchResults at src/agent.ts:9"
FIRST_ADVISORY, FIRST_FIX = "CVE-2026-26019", "1.1.14"
SECOND_ADVISORY, SECOND_FIX = "CVE-2026-27795", "1.1.18"
JS_CVSS_VECTOR = "CVSS:3.1/AV:N/AC:L/PR:L/UI:R/S:C/C:L/I:N/A:N"
JS_CVSS_SOURCE = "ghsa"

ADVISORY_PIN = {
    "advisory_generator_name": trivy_runner.GENERATOR_NAME,
    "advisory_generator_version": TRIVY_VERSION,
    "advisory_db_updated_at": DB_UPDATED_AT,
}


def js_advisories() -> dict:
    """The purl-keyed index the JS fixture's audit reads, built fresh per caller."""
    return {
        JS_COMPONENT_PURL: [
            advisory_record(FIRST_ADVISORY, FIRST_FIX, JS_CVSS_VECTOR, JS_CVSS_SOURCE),
            advisory_record(SECOND_ADVISORY, SECOND_FIX, JS_CVSS_VECTOR, JS_CVSS_SOURCE),
        ],
    }


def advisory_document(*findings: Finding) -> dict:
    """A findings document pinned to an advisory snapshot, as the VEX emitter reads it."""
    surfaces = {finding.surface_id for finding in findings}
    return build_findings_document(
        list(findings), [],
        coverage(len(surfaces), [known_advisory.CHECK_NAME], ADVISORY_SNAPSHOT,
                 risk_classes_checked=[known_advisory.OWASP_ID], **ADVISORY_PIN),
        model_run(MODEL_DISABLED),
    )


def stub_trivy(monkeypatch: pytest.MonkeyPatch, report: dict | None = None,
               date: str = DB_UPDATED_AT) -> None:
    """Make Trivy present with a cached database, without any process starting.

    Applied after `stub_syft`, which turns `is_available` off: these tests are
    the ones that need the advisory path ON, still with no subprocess and no
    dependence on what this machine has installed.
    """
    monkeypatch.setattr(trivy_runner, "is_available", lambda: True)
    monkeypatch.setattr(trivy_runner, "db_snapshot_date", lambda cache_dir=None: date)
    built = report if report is not None else trivy_report(trivy_vulnerability())
    monkeypatch.setattr(trivy_runner, "scan", lambda app_dir, cache_dir=None: built)
