"""The audit artefact: the whole record as JSON, re-derivable without this tool.

Every score travels beside the vector it came from, so a reader with the
published equations reproduces it. Sources are a list and not a set of fields:
`docs/SCORING_MODEL.md` forbids a field anchored to NVD, which is absent from 14
of the 18 findings on the repository under test, and forbids naming a winner
before the council settles one. The list is in source-name order, which is not a
ranking.

Deterministic bytes: keys are written in a fixed order, every collection is
sorted by something stable, and nothing here reads a clock. Two runs over one
tree produce identical output, which is what makes a diff of two reports mean
something.
"""

import json
from typing import Any

from report.disagreement import (
    bands_crossed,
    carries_a_refused_source,
    score_spread,
    sources_disagree,
)
from report.json_council import council_of
from report.json_risk import approval_of, risk_of
from report.provenance import AdvisoryDatabase
from report.absences import Absence
from report.record import Report

INDENT = 2


def as_json(report: Report) -> str:
    """Render the whole record as the audit artefact, byte for byte the same each run."""
    return json.dumps(as_dictionary(report), indent=INDENT, sort_keys=False) + "\n"


def as_dictionary(report: Report) -> dict[str, Any]:
    """Give the record as plain data, in the order a reader meets it."""
    return {
        "run": run_of(report),
        "findings": [finding_of(report, finding) for finding in report.findings],
        "components_without_findings": list(report.components_without_findings),
        "advisories_without_components": list(report.advisories_without_components),
        "overrides_without_findings": list(report.overrides_without_findings),
        "unidentified_artifacts": [
            artifact_of(one) for one in report.unidentified_artifacts
        ],
        "approval": approval_of(report),
        "not_assessed": [absence_of(absence) for absence in report.not_assessed],
    }


def run_of(report: Report) -> dict[str, Any]:
    """Say what produced this report, including whether a database was there to read."""
    provenance = report.provenance
    return {
        "repository": provenance.repository,
        "syft_version": provenance.syft_version,
        "trivy_version": provenance.trivy_version,
        "advisory_database": database_of(provenance.database),
        "component_count": report.component_count,
        "finding_count": len(report.findings),
        # Readable sources only: a vector the calculator refused is not counted
        # as a dissent, whatever it says.
        "findings_whose_sources_disagree": sum(
            1 for finding in report.findings if sources_disagree(finding)
        ),
        # Counted apart, at none as well: a refused vector cannot be compared, so
        # it is no dissent, and it is not an agreement either.
        "findings_with_a_refused_source": sum(
            1 for finding in report.findings if carries_a_refused_source(finding)
        ),
    }


def database_of(database: Any) -> dict[str, Any]:
    """Give the database's build date, or say plainly that none could be read."""
    # A scan against no database finds nothing and exits 0, so "unknown" here is
    # the difference between a clean repository and a report that means nothing.
    if isinstance(database, AdvisoryDatabase):
        return {"built_at": database.built_at, "known": True}
    return {"known": False, "reason": database.reason}


def finding_of(report: Report, finding: Any) -> dict[str, Any]:
    """Give one finding with every source's assessment beside every other's."""
    return {
        "component": component_of(finding),
        "advisory": advisory_of(finding),
        "scores": [score_of(score) for score in finding.scores],
        "unreadable": [unreadable_of(source) for source in finding.unreadable],
        "disputed_metrics": list(finding.disputed_metrics()),
        "score_spread": score_spread(finding),
        "severity_bands": list(bands_crossed(finding)),
        "council": council_of(report, finding.advisory.advisory_id),
        "organisation_risk": risk_of(report, finding.advisory.advisory_id),
    }


def component_of(finding: Any) -> dict[str, Any]:
    """Name the installed component a finding was raised against."""
    component = finding.component
    return {
        "name": component.name,
        "version": component.version,
        "purl": component.purl,
        "ecosystem": component.ecosystem,
        "locations": list(component.locations),
    }


def advisory_of(finding: Any) -> dict[str, Any]:
    """Name the advisory, and the fix if one is published."""
    advisory = finding.advisory
    return {
        "advisory_id": advisory.advisory_id,
        "summary": advisory.summary,
        "fixed_version": advisory.fixed_version,
    }


def score_of(score: Any) -> dict[str, Any]:
    """Give one source's published vector and the number derived from it."""
    # Both, always: the vector is what makes the number checkable by hand.
    return {"source": score.source, "vector": score.vector, "base_score": score.base_score}


def unreadable_of(source: Any) -> dict[str, Any]:
    """Give one source this calculator refused, kept rather than scored zero."""
    return {"source": source.source, "vector": source.vector, "refusal": source.refusal}


def artifact_of(artifact: Any) -> dict[str, Any]:
    """Name one thing Syft catalogued that no advisory could ever be joined to."""
    return {
        "name": artifact.name,
        "ecosystem": artifact.ecosystem,
        "locations": list(artifact.locations),
    }


def absence_of(absence: Absence) -> dict[str, str]:
    """Give one thing this report does not carry, and why it does not."""
    return {"what": absence.what, "because": absence.because}
