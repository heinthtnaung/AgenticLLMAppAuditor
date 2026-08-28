"""Assembles findings.json: the findings, the checks, and what was not covered.

Kept apart from `finding.py`, which owns the records. This module owns the
document: the cross-record rules a single record cannot check, and the
serialisation that keeps the evidence byte-identical while the model's prose
is free to vary.
"""

import json
from dataclasses import asdict

from artifacts.finding import (
    CONFIRMED,
    PROBE,
    SCHEMA_VERSION,
    Finding,
    Probe,
    sort_key,
)

# Whether the model wrote anything this run, and why not when it did not.
MODEL_USED = "used"
MODEL_UNAVAILABLE = "unavailable"
MODEL_DISABLED = "disabled"
MODEL_STATUSES = (MODEL_USED, MODEL_UNAVAILABLE, MODEL_DISABLED)

# Whether advisory data was read. `not_ingested` is today's only real answer:
# advisory ingestion is Phase 2's one unfinished item, so an LLM03 finding
# cites the SBOM and the mapping but nothing about what is known to be wrong.
ADVISORY_NOT_INGESTED = "not_ingested"
ADVISORY_SNAPSHOT = "snapshot"

# The two fields the model writes. Everything else is byte-identical across
# runs and stays under the determinism comparison.
MODEL_AUTHORED_DOCUMENT_FIELD = "ranking"
MODEL_AUTHORED_FINDING_FIELD = "narrative"


def model_run(status: str, identifier: str | None = None,
              settings: dict | None = None, ranking: list[str] | None = None) -> dict:
    """Record what produced the prose, so a later run can repeat it."""
    if status not in MODEL_STATUSES:
        raise ValueError(f"unknown model status {status!r}; expected one of {MODEL_STATUSES}")
    if status != MODEL_USED and identifier is not None:
        raise ValueError(f"{status} names no model")
    if status == MODEL_USED and not identifier:
        raise ValueError("a used model must be named")
    return {
        "status": status,
        "model_identifier": identifier,
        "model_settings": dict(settings or {}),
        MODEL_AUTHORED_DOCUMENT_FIELD: ranking,
    }


def coverage(surfaces_considered: int, checks_run: list[str],
             advisory_data: str = ADVISORY_NOT_INGESTED) -> dict:
    """Say what the search covered, so a short findings list is not read as a clean bill."""
    if surfaces_considered < 0:
        raise ValueError(f"surfaces_considered must not be negative, got {surfaces_considered}")
    if advisory_data not in (ADVISORY_NOT_INGESTED, ADVISORY_SNAPSHOT):
        raise ValueError(f"unknown advisory state {advisory_data!r}")
    return {
        "surfaces_considered": surfaces_considered,
        "checks_run": sorted(checks_run),
        "advisory_data": advisory_data,
    }


def _check_probe_citations(findings: list[Finding], probes: list[Probe]) -> None:
    """A probe finding must name a probe that ran and confirmed it.

    This cannot live on the record: it spans the document, and a finding built
    alone has no way to see the probe list.
    """
    confirmed = {probe.id for probe in probes if probe.outcome == CONFIRMED}
    for finding in findings:
        if finding.detection == PROBE and finding.probe_id not in confirmed:
            raise ValueError(f"{finding.id} cites {finding.probe_id!r}, which confirmed nothing")


def _check_unique_ids(findings: list[Finding]) -> None:
    """Ids must be unique, because the model's ranking is a permutation of them."""
    seen = [finding.id for finding in findings]
    if len(set(seen)) != len(seen):
        raise ValueError("two findings share an id; the same finding was reported twice")


def build_findings_document(findings: list[Finding], probes: list[Probe],
                            document_coverage: dict, run: dict) -> dict:
    """Return the findings document, refusing one whose parts contradict each other."""
    _check_probe_citations(findings, probes)
    _check_unique_ids(findings)
    ordered = sorted(findings, key=sort_key)
    ranking = run.get(MODEL_AUTHORED_DOCUMENT_FIELD)
    if ranking is not None and sorted(ranking) != sorted(f.id for f in ordered):
        raise ValueError("the model's ranking must be a permutation of every finding id")
    return {
        "schema_version": SCHEMA_VERSION,
        "coverage": document_coverage,
        "model_run": run,
        "probe_count": len(probes),
        "probes": [{**asdict(p), "probe_id": p.id} for p in sorted(probes, key=lambda p: p.id)],
        "finding_count": len(ordered),
        "findings": [{**asdict(f), "finding_id": f.id} for f in ordered],
    }


def strip_model_authored(document: dict) -> dict:
    """Return the document without the two fields a model wrote.

    What is left is byte-identical across runs, so the evidence keeps the
    guarantee every other artifact makes while the prose is exempt from it.
    """
    stripped = json.loads(json.dumps(document))
    stripped["model_run"].pop(MODEL_AUTHORED_DOCUMENT_FIELD, None)
    for finding in stripped["findings"]:
        finding.pop(MODEL_AUTHORED_FINDING_FIELD, None)
    return stripped


def findings_to_json(document: dict) -> str:
    """Serialise the findings document to its stable on-disk form."""
    return json.dumps(document, indent=2, sort_keys=True) + "\n"
