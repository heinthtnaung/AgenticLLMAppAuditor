"""One audit, end to end: scan, join, score, and gather the record.

Nothing here decides anything. Every step is a package that was built and tested
on its own, and this is the order they go in -- which is why the file is short
and why it is the only place that knows the order.

**The scanner versions are asked, not configured.** A provenance field somebody
types is a claim nobody checked, and the one purpose of that field is to make a
run checkable. This is how a report came to print `trivy 0.58.1` on a machine
running 0.74.0 while nothing was wrong with the report.
"""

from pathlib import Path

from deps import syft_runner, trivy_runner
from findings.finding import build_findings
from report.record import AdvisoryDatabase, Report, RunProvenance, build_report

from cli.arguments import Options
from cli.council_run import assessments, build_roster


def run_audit(options: Options, database_built_at: str) -> Report:
    """Scan one repository against the pinned database and gather everything into a record."""
    catalogue = syft_runner.scan_directory(options.repository)
    advisories = trivy_runner.scan_directory(options.repository)
    findings = build_findings(catalogue.components, advisories)
    return build_report(
        provenance=provenance_of(options.repository, database_built_at),
        catalogue=catalogue,
        findings=findings,
        advisories_by_purl=advisories,
        council=council_of(findings, options),
    )


def provenance_of(repository: Path, database_built_at: str) -> RunProvenance:
    """Record what produced this run, asking each tool its own version."""
    return RunProvenance(
        repository=str(repository),
        syft_version=syft_runner.installed_version(),
        trivy_version=trivy_runner.installed_version(),
        database=AdvisoryDatabase(built_at=database_built_at),
    )


def council_of(findings, options: Options):
    """Put the council to the findings, or run none, which is the default."""
    if not options.council_models:
        return ()
    return assessments(findings, build_roster(options.council_models))
