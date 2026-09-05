"""Re-emits the findings as SARIF, the standard format for static-analysis results.

Separate from `findings_document.py` because the two answer different questions,
exactly as `cyclonedx.py` is separate from `sbom.py`. That file builds this
project's contract, which records what was *not* examined as carefully as what
was; this one hands the findings to other tooling in the format that tooling
reads, and SARIF has nowhere to put that judgement.

**A findings list with no caveat attached is the misreading this project is
built to prevent**, so `coverage` travels with it in the run's property bag
rather than being left behind. Every field of it is deterministic, so carrying
it costs nothing the byte-identity rule protects. What still does not survive is
`surfaces.json`'s `skipped_files`, which lives in another artifact entirely, and
the probe records themselves -- only their count crosses. The document names
`findings.json` for those, and is never the file Phase 4 scores.

Unlike `report.py`, this module does not refuse a stale `schema_version`. It is
only ever called on the in-memory document the run just built, never on a file
read back from disk, so there is no stale version for it to meet. That is a
decision rather than an oversight; the day anything converts a document off
disk, it needs the same guard `report.py` has.

`narrative` is deliberately dropped. It is the one model-authored field a
finding can carry, and exporting unverifiable prose into other people's tools
would also drag this artifact into the determinism exemption for no consumer's
gain. Nothing here is exempt: the file is byte-identical every run.
"""

import json

SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
SARIF_VERSION = "2.1.0"

# No `version`. This project has no version number -- no pyproject.toml, no
# __version__ -- and every candidate is a fact-shaped guess: a literal is
# pinned to nothing, and a commit hash moves the artifact when the input did
# not. The field is optional in SARIF, so it is absent rather than invented.
# Syft's `generator_version` is not a counter-example: Syft can be asked.
DRIVER_NAME = "agentic-llm-app-auditor"

# One constant on every result. SARIF resolves an absent level to `warning`
# anyway, so this is the value that adds no claim -- and this project reports
# no severity, because nothing in a grading key could check one. A per-result
# level would be a new unfalsifiable judgement made in a file that is a copy.
RESULT_LEVEL = "warning"

# The file that carries what SARIF cannot: coverage, probes, skipped files.
FINDINGS_ARTIFACT = "findings.json"

# Copied onto a result so a consumer never has to parse a surface id, which the
# contract forbids. `owasp_id` is absent on purpose: it is constant on the rule
# and lives there, so one fact has one home.
RESULT_PROPERTIES = (
    "finding_id", "surface_id", "surface_kind", "surface_name",
    "purl", "component_name", "mapping_reason", "detection", "probe_id",
    # rule_id stays in the bag on purpose: an advisory finding's ruleId below
    # is its CVE/GHSA id, and the check name must not be lost from the copy.
    "rule_id",
    "advisory_id", "advisory_fixed_version",
    "advisory_cvss_vector", "advisory_severity", "advisory_cvss_source",
)


def _rule_id(finding: dict) -> str:
    """The advisory id when there is one, else the check name."""
    # The one deliberate departure in this derived copy: the standard filter
    # joins on ruleId being a CVE-/GHSA-scheme identifier and nothing else, so
    # this is what makes a finding addressable by a maintainer's statement.
    return finding.get("advisory_id") or finding["rule_id"]


def _location(finding: dict) -> list[dict]:
    """Point at the code, or at nothing when the finding has no location to give."""
    if not finding.get("file"):
        return []
    physical: dict = {"artifactLocation": {"uri": finding["file"]}}
    if finding.get("line"):
        physical["region"] = {"startLine": finding["line"]}
    return [{"physicalLocation": physical}]


def _result(finding: dict) -> dict:
    """Convert one finding, carrying its evidence in the property bag."""
    properties = {name: finding[name] for name in RESULT_PROPERTIES
                  if finding.get(name) is not None}
    return {
        # Required in practice, not just by the schema: vexctl segfaults on a
        # result without one.
        "ruleId": _rule_id(finding),
        "level": RESULT_LEVEL,
        "message": {"text": finding["title"]},
        "locations": _location(finding),
        "properties": properties,
    }


def _rules(findings: list[dict]) -> list[dict]:
    """Describe only the rules that produced a result here, sorted by id.

    An unfired rule has no defined meaning in SARIF, and a reader would take it
    for "ran and found nothing" -- the claim `coverage.checks_run` is careful to
    make only when it is true. Saying nothing is the safe move.
    """
    seen: dict[str, dict] = {}
    for finding in findings:
        seen.setdefault(_rule_id(finding), {
            "id": _rule_id(finding),
            "shortDescription": {"text": finding["title"]},
            "properties": {"owasp_id": finding["owasp_id"]},
        })
    return [seen[rule_id] for rule_id in sorted(seen)]


def to_sarif(findings_document: dict) -> dict:
    """Return the findings as a SARIF log, derived wholly from the document given."""
    findings = findings_document["findings"]
    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [{
            "tool": {"driver": {"name": DRIVER_NAME, "rules": _rules(findings)}},
            "results": [_result(finding) for finding in findings],
            "properties": {
                # The contract this was derived from: what invalidates the file,
                # in place of a timestamp that would break byte-identity.
                "findings_schema_version": findings_document["schema_version"],
                "findings_artifact": FINDINGS_ARTIFACT,
                # Carried, not dropped. SARIF has no native place for "this
                # check ran and stayed silent" versus "this check could not
                # look", and a findings list without it reads as a clean bill.
                "coverage": findings_document["coverage"],
                "probe_count": findings_document["probe_count"],
            },
        }],
    }


def sarif_to_json(document: dict) -> str:
    """Serialise the SARIF log to its stable on-disk form."""
    return json.dumps(document, indent=2, sort_keys=True) + "\n"
