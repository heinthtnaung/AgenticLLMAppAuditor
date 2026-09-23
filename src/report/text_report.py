"""The record for a terminal, led by the question a reader actually brings to it.

Eighteen findings with up to five sources each is more rows than anyone reads,
and dumping the record would bury the one thing this tool exists to show. So the
findings are split into three groups and **the contested ones come first**,
ordered by how much their disagreement would change a decision: a spread across
a severity band boundary moves the response time, a spread inside one band only
moves a number.

Each contested finding gets three lines -- what it is, how far apart the sources
are and which metrics they read differently, then every source side by side. The
agreeing ones get one line each, because there is nothing to compare. A finding
nobody scored gets its own group rather than a zero.

How a finding itself is written is `report.text_findings`; this file is the page
it goes on.
"""

from report.disagreement import sources_disagree
from report.record import AdvisoryDatabase, CouncilAssessment, Report
from report.text_findings import agreeing_block, contested_block, unscored_block
from report.text_layout import INDENT, SOURCE_SEPARATOR, section

# Wide enough for a path, which is what an unidentifiable artifact is named by.
ARTIFACT_NAME_WIDTH = 42

def as_text(report: Report) -> str:
    """Render the record for a terminal, leading with where the sources disagree."""
    blocks = [
        heading(report),
        summary(report),
        contested_block(report),
        agreeing_block(report),
        unscored_block(report),
        council_block(report),
        unmatched_block(report),
        unidentified_block(report),
        absences_block(report),
    ]
    body = "\n\n".join(block for block in blocks if block)
    # Padding a column leaves trailing spaces on whatever ends a line, and a
    # record whose bytes differ from what it looks like is a poor audit artefact.
    return "\n".join(line.rstrip() for line in body.split("\n")) + "\n"


def heading(report: Report) -> str:
    """Name the repository and what scanned it."""
    run = report.provenance
    tools = f"syft {run.syft_version}{SOURCE_SEPARATOR}trivy {run.trivy_version}"
    return f"Audit of {run.repository}\n{INDENT}{tools}{SOURCE_SEPARATOR}{database_line(run)}"


def database_line(run) -> str:
    """Say when the advisory database was built, or shout that nothing said."""
    # A scan against no database finds nothing and exits 0. That is the one
    # failure a clean-looking report cannot be told from, so it is not quiet.
    if isinstance(run.database, AdvisoryDatabase):
        return f"advisory database built {run.database.built_at}"
    return f"NO ADVISORY DATABASE DATE: {run.database.reason}"


def summary(report: Report) -> str:
    """Say how much there is, and how much of it the sources argue about."""
    contested = len([one for one in report.findings if sources_disagree(one)])
    return (
        f"{len(report.findings)} findings across {report.component_count} components. "
        f"{contested} carry sources that disagree."
    )


def unmatched_block(report: Report) -> str:
    """Count what matched nothing, keeping the two kinds apart."""
    entries = [
        f"{INDENT}{len(report.components_without_findings)} components carry no advisory",
        f"{INDENT}{len(report.advisories_without_components)} advisories matched no component",
    ]
    return section("MATCHED NOTHING", entries)


def council_block(report: Report) -> str:
    """Say what the council did for each advisory, keeping its two outcomes apart.

    Three states a reader has to be able to tell apart: no council ran, which is
    this block being absent and the absence named below; a council settled a
    vector; and a council ran and could not. The last two are both "a council
    ran", and they were indistinguishable from the first until they had their
    own records.
    """
    if not report.council:
        return ""
    width = max(len(advisory_id) for advisory_id in report.council)
    entries = [
        f"{INDENT}{advisory_id.ljust(width)}  {council_line(report.council[advisory_id])}"
        for advisory_id in sorted(report.council)
    ]
    return section(f"COUNCIL ({len(report.council)})", entries)


def council_line(outcome) -> str:
    """Say whether the council handed over a vector, or what stopped it."""
    if isinstance(outcome, CouncilAssessment):
        return f"settled{SOURCE_SEPARATOR}{outcome.vector}"
    still_open = ", ".join(outcome.unresolved_metrics + outcome.contested_metrics)
    return f"no vector{SOURCE_SEPARATOR}could not settle {still_open}"


def unidentified_block(report: Report) -> str:
    """Name what was catalogued and could never be joined, rather than dropping it."""
    catalogued = report.unidentified_artifacts
    if not catalogued:
        return ""
    entries = [
        f"{INDENT}{one.name.ljust(ARTIFACT_NAME_WIDTH)}{one.ecosystem}" for one in catalogued
    ]
    return section(f"COULD NOT BE IDENTIFIED ({len(catalogued)})", entries)


def absences_block(report: Report) -> str:
    """Name what this run did not assess, so no reader reads silence as a nil result."""
    entries = [
        f"{INDENT}{absence.what}\n{INDENT}{INDENT}{absence.because}"
        for absence in report.not_assessed
    ]
    return section("NOT ASSESSED", entries)
