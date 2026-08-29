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

from artifacts.finding import OWASP_IDS, PROBE, SCHEMA_VERSION, UNRESOLVED_OUTCOMES

HEADING = "# Audit report: {app}"

NOTHING_FOUND = "No findings. See what was not examined, below, before reading that as clean."

RISK_TITLES = {
    "LLM01": "Prompt injection",
    "LLM02": "Insecure output handling",
    "LLM03": "Supply chain",
    "LLM06": "Excessive agency",
    "AUDITABILITY": "Inadequate auditability of agent actions",
}


def _plural(count: int, noun: str) -> str:
    """Count a noun so the human report does not print "1 files"."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


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
    located = finding.get("file") and finding.get("line")
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
    lines += _probe_lines(finding, probes)
    if finding.get("narrative"):
        lines += ["", finding["narrative"]]
    return lines + [""]


def _skipped_lines(surfaces_document: dict) -> list[str]:
    """Name the files that could not be read, so their surfaces read as absent, not clean."""
    skipped = surfaces_document["skipped_files"]
    if not skipped:
        return ["Every source file was read.", ""]
    count = _plural(len(skipped), "file")
    return [f"**{count} could not be read**, so any surface in them is "
            "absent from this report rather than absent from the app:"] + \
           [f"- `{s['file']}` — {s['reason']}" for s in skipped] + [""]


def _unresolved_lines(findings_document: dict) -> list[str]:
    """Name the traces that ran out of syntax before reaching a verdict."""
    unresolved = [p for p in findings_document["probes"]
                  if p["outcome"] in UNRESOLVED_OUTCOMES]
    if not unresolved:
        return []
    count = _plural(len(unresolved), "trace")
    # Both: detail is the sentence a person reads, reason the enum they can
    # look up. The enum alone printed nine times is not a human report.
    return [f"**{count} could not be followed.** The value may still "
            "reach a model somewhere the syntax tree cannot show:"] + \
           [f"- `{p['subject_id']}` — {p['detail']} (`{p['reason']}`)" for p in unresolved] + [""]


def _uncovered_risk_lines(coverage: dict) -> list[str]:
    """Name the risk classes no check looked for, which silence would otherwise hide."""
    missing = sorted(set(OWASP_IDS) - set(coverage["risk_classes_checked"]))
    if not missing:
        return []
    named = ", ".join(f"{risk} ({RISK_TITLES.get(risk, risk)})" for risk in missing)
    return [f"**No check covers these risks**, so this report says nothing about them: {named}.", ""]


def _unresolved_component_lines(coverage: dict) -> list[str]:
    """Name the surfaces the supply-chain check had no component to examine."""
    count = coverage["unresolved_component_count"]
    if not count:
        return []
    return [f"**{_plural(count, 'surface')} could not be traced to a component**, so nothing "
            "is said about where that code came from or what it depends on.", ""]


def _advisory_lines(coverage: dict) -> list[str]:
    """Say when a supply-chain finding names a package but nothing known about it."""
    if coverage["advisory_data"] != "not_ingested":
        return []
    return ["**No advisory data was read**, so a supply-chain finding names a package "
            "but not what is known to be wrong with it.", ""]


def _not_examined_lines(findings_document: dict, surfaces_document: dict) -> list[str]:
    """Say what the audit did not reach, in the same detail as what it found."""
    coverage = findings_document["coverage"]
    return (["## What was not examined", ""]
            + _skipped_lines(surfaces_document)
            + _unresolved_lines(findings_document)
            + _unresolved_component_lines(coverage)
            + _uncovered_risk_lines(coverage)
            + _advisory_lines(coverage))


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
        "A check named above that reported nothing looked and found nothing. One that is "
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
    lines = [HEADING.format(app=app), "", "## Findings", ""]
    if findings:
        for finding in findings:
            lines += _finding_lines(finding, probes)
    else:
        lines += [NOTHING_FOUND, ""]
    lines += _not_examined_lines(findings_document, surfaces_document)
    lines += _how_it_was_audited(findings_document)
    return "\n".join(lines)


def render_from_files(app: str, findings_path: Path, surfaces_path: Path) -> str:
    """Render from the two artifacts on disk, which are its only inputs."""
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    surfaces = json.loads(surfaces_path.read_text(encoding="utf-8"))
    return render(app, findings, surfaces)
