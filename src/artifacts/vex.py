"""Decides what VEX statements a findings document implies, and nothing beyond it.

Three readings of one document and no side effects: which claims it supports,
the schema it must be for those claims to exist, and the instant they are
dated from.

The pure half of the emitter, beside `sarif.py` for the same reason: both turn
`findings.json` into a standard format other tooling reads, and neither is the
contract. This module builds no JSON -- `vexctl` writes the document, because
OpenVEX is a spec this project does not own. What is decided here is only the
claim: which component, which advisory, and the evidence for saying so.

**The audited app is the product; the component is a subcomponent of it.** That
is the whole difference between a document worth publishing and one that just
restates the advisory. "This component is affected by this CVE" is the
component publisher's claim to make and is already in the database; "*this app*
is affected via this component, and here is the surface that reaches it" is
what this project measured and what nothing else can assert.

**Two statuses, and `not_affected` is not one of them.** A component an LLM
surface reaches is `affected`, with the surface as the evidence. A component
that carries an advisory but no surface reaches is `under_investigation`: the
tool found the CVE but assesses reachability only through LLM surfaces, so it
has *not* determined real-world exploitability. It never says `not_affected` --
"no LLM surface reaches it" is not "the vulnerable code is unreachable", because
the mapping holds one entry per LLM surface and an app's ordinary code is not in
it, so `not_affected` would suppress a real vulnerability. `under_investigation`
suppresses nothing.
"""

from datetime import datetime

from artifacts.finding import SCHEMA_VERSION

AFFECTED = "affected"
UNDER_INVESTIGATION = "under_investigation"

# Every status this tool may emit -- and the ban's other half: `not_affected`
# is not here, so it can never be written.
EMITTABLE_STATUSES = (AFFECTED, UNDER_INVESTIGATION)

# Why an unreached component is under_investigation, not a verdict either way.
UNREACHED_NOTE = ("Present in a dependency; not reached by any LLM surface, so "
                  "this tool has not assessed real-world exploitability.")

# Fractional seconds beyond microseconds, which `fromisoformat` will not read.
MICROSECOND_DIGITS = 6

# Set explicitly on every statement: vexctl's default is the placeholder
# "No action statement provided", which would ship as though it were a finding.
NO_FIX = "No fixed version is recorded in the pinned advisory database"


def _reaching_surface(finding: dict) -> str:
    """Name one surface that reaches the component, as a reader would cite it."""
    return f"{finding['surface_name']} at {finding['file']}:{finding['line']}"


def _status_note(findings: list[dict]) -> str:
    """How the status was determined: every surface that reaches the component."""
    ordered = sorted(findings, key=lambda one: (one["file"], one["line"]))
    return "Reached by " + ", ".join(_reaching_surface(one) for one in ordered)


def advisory_findings(findings_document: dict) -> list[dict]:
    """Only the findings that carry an advisory; every other check says nothing here."""
    return [finding for finding in findings_document["findings"]
            if finding.get("advisory_id")]


def to_vex_statements(findings_document: dict) -> list[dict]:
    """One statement per (advisory, component), whatever the surface count.

    Deduplicated on purpose. `known_advisory` reports one finding per (surface,
    component, advisory), so two surfaces reaching one vulnerable component are
    two findings -- but two statements with the same product, vulnerability,
    status and timestamp are not a richer document: OpenVEX resolves competing
    statements by timestamp, and identical timestamps leave no precedence. The
    surfaces are not lost; they are named together in the status note.
    """
    grouped: dict[tuple[str, str], list[dict]] = {}
    for finding in advisory_findings(findings_document):
        grouped.setdefault((finding["advisory_id"], finding["purl"]), []).append(finding)
    affected = [_affected(advisory, purl, group)
                for (advisory, purl), group in sorted(grouped.items())]
    return affected + _under_investigation(findings_document["coverage"])


def _affected(advisory: str, purl: str, group: list[dict]) -> dict:
    """A reached component: affected, with the reaching surface as the evidence."""
    fixes = {one["advisory_fixed_version"] for one in group if one["advisory_fixed_version"]}
    return {
        "vulnerability": advisory,
        "subcomponent": purl,
        "status": AFFECTED,
        "status_note": _status_note(group),
        # Quoted from the database, never composed: what to actually do about it
        # is remediation advice, which is model-authored and lives elsewhere.
        "action_statement": ", ".join(sorted(fixes)) if fixes else NO_FIX,
    }


def _under_investigation(coverage: dict) -> list[dict]:
    """Unreached components: present, but exploitability not assessed by this tool.

    One statement per (component, advisory), from the coverage list -- never a
    finding, because nothing reaches these. `action_statement` is `None`: it is
    an `affected`-only field, and there is no verdict to act on here.
    """
    items = coverage.get("advisory_unreached_components") or []
    return [
        {"vulnerability": advisory["id"], "subcomponent": item["purl"],
         "status": UNDER_INVESTIGATION, "status_note": UNREACHED_NOTE,
         "action_statement": None}
        for item in items for advisory in item["advisories"]
    ]


def check_readable(findings_document: dict) -> None:
    """Refuse a findings.json older than the fields this document is built from.

    The emitter is the first thing besides `report.py` to read that file back
    off disk, the condition `sarif.py` wrote down as needing this guard: a
    stale document has no advisory pin, so the failure would otherwise be a
    KeyError rather than a sentence a reader can act on.
    """
    version = findings_document.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"findings.json is schema_version {version}; emitting VEX needs "
            f"{SCHEMA_VERSION}. Regenerate it - an older file records no advisory "
            "pin, so there is no instant to date a statement from")


def pinned_epoch(coverage: dict) -> str:
    """The advisory database's own date, as the epoch seconds vexctl reads."""
    taken = coverage["advisory_db_updated_at"]
    if not taken:
        raise ValueError(
            "this audit read no advisory data, so there is nothing to state and "
            "no date to pin a statement to. Re-run the audit with the advisory "
            "generator available - see the README prerequisites")
    trimmed = taken.rstrip("Z")
    if "." in trimmed:
        whole, fraction = trimmed.split(".", 1)
        trimmed = f"{whole}.{fraction[:MICROSECOND_DIGITS]}"
    return str(int(datetime.fromisoformat(f"{trimmed}+00:00").timestamp()))
