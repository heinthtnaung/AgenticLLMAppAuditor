"""Renders findings.json and surfaces.json as a report a person can read.

A rendering, not a producer: every fact here comes from those two files, and
nothing is recomputed from source. A second producer of the same facts is a
second place for them to disagree, which is why `target.json` was declined.

What was *not* examined is given the same prominence as what was found. A short
findings list is not a clean bill, and a report that only lists findings invites
being read as one.

Scoring belongs to Phase 4. This file names findings and gaps; it never counts
them into a rate, so no precision, recall or "detected N of M" appears here.
"""

import json
from pathlib import Path

from artifacts.finding import PROBE, SCHEMA_VERSION, is_located
from report_gaps import (
    RISK_TITLES, dependency_vulnerability_lines, not_examined_lines, vex_summary_lines)

HEADING = "# Audit report: {app}"

NOTHING_FOUND = "No findings. See what was not examined, below, before reading that as clean."

NOTHING_REACHED = ("No finding reaches an LLM surface. That is not a clean bill: known "
                   "vulnerabilities in this app's dependencies are listed below, and what "
                   "was not examined follows them.")


def _probe_lines(finding: dict, probes: dict) -> list[str]:
    """Name the probe behind a probe-detected finding, and what it observed.

    A finding that says only "probe analysis" asserts evidence without showing
    it, in a report whose whole point is that every claim carries its own.
    """
    probe = probes.get(finding.get("probe_id"))
    if probe:
        return [f"- **Probe**: `{probe['probe_id']}` — {probe['detail']}"]
    # A static finding cites no probe, which is correct and renders nothing. A
    # probe finding whose probe is missing would render "probe analysis" with
    # no evidence under it -- asserting a claim and showing nothing for it.
    if finding["detection"] == PROBE:
        raise ValueError(
            f"{finding['finding_id']} says a probe reached it but names "
            f"{finding['probe_id']!r}, which is not in this document")
    return []


def _finding_lines(finding: dict, probes: dict) -> list[str]:
    """Render one finding with the evidence that produced it."""
    risk = RISK_TITLES.get(finding["owasp_id"], finding["owasp_id"])
    located = is_located(finding)
    where = f"{finding['file']}:{finding['line']}" if located else "no code location"
    lines = [
        f"### {finding['owasp_id']} — {finding['title']}",
        "",
        f"- **Where**: `{where}`",
        f"- **Risk**: {risk} ({finding['owasp_id']}, OWASP 2025 list)",
        f"- **Reached by**: `{finding['rule_id']}`, {finding['detection']} analysis",
    ]
    if finding.get("surface_id"):
        lines.append(f"- **Surface**: `{finding['surface_id']}`")
    if finding.get("component_name"):
        component = finding.get("purl") or finding["component_name"]
        lines.append(f"- **Component**: `{component}`")
    if finding.get("mapping_reason"):
        lines.append(f"- **Mapping**: {finding['mapping_reason']}")
    lines += _advisory_evidence(finding)
    lines += _probe_lines(finding, probes)
    if finding.get("narrative"):
        lines += ["", finding["narrative"]]
    return lines + [""]


def _advisory_evidence(finding: dict) -> list[str]:
    """Quote the advisory a finding cites: its id, the fix, the vector, and its VEX status."""
    if not finding.get("advisory_id"):
        return []
    fix = finding.get("advisory_fixed_version")
    lines = [f"- **Advisory**: `{finding['advisory_id']}`, "
             + (f"fixed in `{fix}`" if fix else "no fixed version published")]
    if finding.get("advisory_severity"):
        lines.append(f"- **Severity**: {finding['advisory_severity']} "
                     f"(per {finding['advisory_cvss_source']})")
    if finding.get("advisory_cvss_vector"):
        lines.append(f"- **CVSS ({finding['advisory_cvss_source']}, quoted)**: "
                     f"`{finding['advisory_cvss_vector']}`")
    # Says what this finding *would become*, not what a file already says: the
    # OpenVEX document is written by `src/emit_vex.py`, a command of its own
    # that also needs vexctl, so it need not exist when this report is read.
    # Every such statement is `affected`; this project refuses to author the
    # negative form, and `tests/test_vexctl_launch.py` enforces that by banning
    # the phrase as a *value* anywhere under `src/` -- which is why that is
    # said here rather than in the rendered line.
    lines.append(f"- **VEX Status**: carries `{finding['advisory_id']}`, so "
                 "`python src/emit_vex.py` would state it as `affected` — a "
                 "component a surface reaches.")
    return lines


def _how_it_was_audited(findings_document: dict) -> list[str]:
    """Record what ran, so a silent check is not mistaken for an absent one."""
    coverage = findings_document["coverage"]
    run = findings_document["model_run"]
    model = (f"`{run['model_identifier']}`" if run["status"] == "used"
             else f"not used ({run['status']})")
    return [
        "## How it was audited", "",
        f"- **Surfaces considered**: {coverage['surfaces_considered']}",
        f"- **Checks that had something to examine**: {', '.join(coverage['checks_run']) or 'none'}",
        f"- **Risk classes covered**: {', '.join(coverage['risk_classes_checked']) or 'none'}",
        f"- **Local model**: {model}",
        "",
        "A check named above that reported nothing looked and found nothing, unless it appears in `checks_narrowed` -- then it looked at only some of its surfaces, and the counts there say how many. One that is "
        "absent could not look at all.",
        "",
    ]


def _check_readable(findings_document: dict) -> None:
    """Refuse a findings.json older than the fields this report is built on."""
    version = findings_document.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"findings.json is schema_version {version}; this report needs "
            f"{SCHEMA_VERSION}. Regenerate it — an older file cannot say which "
            "risk classes went unchecked, nor how many surfaces had no component.")


def render(app: str, findings_document: dict, surfaces_document: dict) -> str:
    """Return the whole report as Markdown."""
    _check_readable(findings_document)
    findings = findings_document["findings"]
    probes = {p["probe_id"]: p for p in findings_document["probes"]}
    coverage = findings_document["coverage"]
    dependency_vulns = dependency_vulnerability_lines(coverage)
    lines = [HEADING.format(app=app), "", "## Findings", ""]
    if findings:
        for finding in findings:
            lines += _finding_lines(finding, probes)
    elif dependency_vulns:
        lines += [NOTHING_REACHED, ""]
    else:
        lines += [NOTHING_FOUND, ""]
    lines += dependency_vulns
    lines += vex_summary_lines(findings_document)
    lines += not_examined_lines(findings_document, surfaces_document)
    lines += _how_it_was_audited(findings_document)
    return "\n".join(lines)


def render_from_files(app: str, findings_path: Path, surfaces_path: Path) -> str:
    """Render from the two artifacts on disk, which are its only inputs."""
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    surfaces = json.loads(surfaces_path.read_text(encoding="utf-8"))
    return render(app, findings, surfaces)
