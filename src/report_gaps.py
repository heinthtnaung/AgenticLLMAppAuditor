"""Renders the report's caveat sections: the vulnerable components, the VEX
counts, and what was not examined.

Split from `report.py`, which renders the findings; this file renders their
limits. These sections are the report's honesty mechanism -- a short findings
list without them reads as a clean bill -- so they get a module of their own
rather than the bottom half of another.

Two source guards watch this file, and the prose above obeys them rather than
asking for an exemption: the machine words `not_affected` and the emitter's own
command are spelled in English here, because a module that spelled them as
values would be indistinguishable from one that had started making the claim or
reading the document.
"""

from artifacts.finding import OWASP_IDS, UNRESOLVED_OUTCOMES
from artifacts.findings_document import ADVISORY_NOT_INGESTED
from artifacts.vex import AFFECTED, UNDER_INVESTIGATION, to_vex_statements

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
    """Advisory provenance or its absence: an unpinned scan is an undated claim."""
    if coverage["advisory_data"] == ADVISORY_NOT_INGESTED:
        return ["**No advisory data was read**, so a supply-chain finding names a package "
                "but not what is known to be wrong with it.", ""]
    lines = [f"Known-vulnerability data: `{coverage['advisory_generator_name']}` "
             f"{coverage['advisory_generator_version']}, database of "
             f"`{coverage['advisory_db_updated_at']}`.", ""]
    unreached = coverage["advisory_unreached_component_count"]
    if not unreached:
        return lines
    return lines + [f"**{_plural(unreached, 'component')} with a known advisory "
                    "reached by no LLM surface**, listed in full under "
                    '"Known vulnerabilities in dependencies" above.', ""]


DEPENDENCY_VULN_HEADING = "## Known vulnerabilities in dependencies"


def dependency_vulnerability_lines(coverage: dict) -> list[str]:
    """Itemize the vulnerable components no LLM surface reaches, prominently.

    These are real, from the advisory database, and were formerly reported only
    as a count -- so a repository full of vulnerable packages read as clean.
    They are listed here in full, and deliberately kept out of the scored
    findings above: a finding in this tool means a vulnerable component an LLM
    surface can actually reach, and nothing reaches these.
    """
    items = coverage.get("advisory_unreached_components")
    if not items:
        return []
    lead = (f"**{_plural(len(items), 'component')} carry a known advisory** "
            f"(via `{coverage['advisory_generator_name']}` "
            f"{coverage['advisory_generator_version']}, database of "
            f"`{coverage['advisory_db_updated_at']}`). None is reached by an LLM "
            "surface, so none is a scored finding of this tool -- but they are "
            "real, and an ordinary dependency scanner would flag every one:")
    rows = [f"- `{item['purl']}` — {_advisories_with_severity(item)}" for item in items]
    return [DEPENDENCY_VULN_HEADING, "", lead, ""] + rows + [""]


def _advisories_with_severity(item: dict) -> str:
    """Each CVE with its severity when the database rated it, else just the id.

    Attributed at the section level -- the lead line names the generator
    (`trivy`) and its database -- rather than repeating "(per ghsa)" on every
    one of hundreds of CVEs. The few reached findings carry per-source
    attribution inline.
    """
    return ", ".join(
        f"{a['id']} ({a['severity']})" if a["severity"] else a["id"]
        for a in item["advisories"])


VEX_HEADING = "## VEX (exploitability statements)"


def vex_summary_lines(findings_document: dict) -> list[str]:
    """Count the VEX statements this audit implies, by status, from one source.

    Reads the same `to_vex_statements` the emitter writes from, so the report's
    counts equal the document's by construction -- never a second, drifting
    tally. Rendered only when a snapshot ran and there is something to state.
    """
    if findings_document["coverage"]["advisory_data"] == ADVISORY_NOT_INGESTED:
        return []
    statements = to_vex_statements(findings_document)
    if not statements:
        return []
    affected = sum(1 for s in statements if s["status"] == AFFECTED)
    investigating = sum(1 for s in statements if s["status"] == UNDER_INVESTIGATION)
    return [VEX_HEADING, "",
            f"**{_plural(affected, 'affected statement')}** (a vulnerable component "
            "an LLM surface reaches) and "
            f"**{investigating} under_investigation** (present in a dependency, "
            "reachability not assessed -- this tool never claims that a component "
            "is not affected). "
            "Emitted as OpenVEX by this project's VEX emitter command (see the "
            "README), product = the audited app, so a downstream tool can consume "
            "them.", ""]


def not_examined_lines(findings_document: dict, surfaces_document: dict) -> list[str]:
    """Say what the audit did not reach, in the same detail as what it found."""
    coverage = findings_document["coverage"]
    return (["## What was not examined", ""]
            + _skipped_lines(surfaces_document)
            + _unresolved_lines(findings_document)
            + _unresolved_component_lines(coverage)
            + _uncovered_risk_lines(coverage)
            + _advisory_lines(coverage))
