"""The record as one HTML file: self-contained, offline, and readable without scripts.

**Nothing is fetched at any point.** A scan runs behind a corporate proxy and
the page is opened from a file, so the stylesheet is inlined and there is no
script, no font, no image and no link out. A report that fetched a stylesheet
would arrive unreadable in the environment it was made for.

**Nothing here computes a number.** Every figure is the one the engine put in
the record, rendered beside the vector or the answer it came from. A second
place a score could be worked out is a second place it could differ.

The order is the terminal rendering's order, for the same reason: the contested
findings lead, because a disagreement that crosses a severity band changes the
response time, and what the run did not assess is last and never cut.
"""

from report.disagreement import sources_disagree
from report.html_absences import (
    approval_section,
    council_section,
    matched_nothing_section,
    not_assessed_section,
    unidentified_section,
)
from report.html_findings import agreeing_section, contested_section, unscored_section
from report.html_layout import separated, tag, text
from report.html_risk import risk_section
from report.html_style import STYLESHEET
from report.provenance import AdvisoryDatabase
from report.record import Report

DOCTYPE = "<!DOCTYPE html>"
LANGUAGE = "en"
CHARSET = '<meta charset="utf-8">'
VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1">'

LEGEND = (
    "Two claims appear on this page and are never merged. A published CVSS base score runs "
    "0.0 to 10.0 and belongs to the source that published it; the Organisation Risk Score "
    "runs 0 to 100 and is this system's own. A finding that is CVSS Critical and "
    "organisation Low is the normal case, not an error."
)


def as_html(report: Report) -> str:
    """Render the whole record as one page, leading with where the sources disagree."""
    blocks = [
        run_header(report),
        legend(),
        contested_section(report),
        agreeing_section(report),
        unscored_section(report),
        risk_section(report),
        council_section(report),
        matched_nothing_section(report),
        unidentified_section(report),
        approval_section(report),
        not_assessed_section(report),
    ]
    return document(title_of(report), tag("main", "".join(blocks)))


def document(title: str, body: str) -> str:
    """Put the page together: no script, no link, nothing fetched at any point."""
    page = [DOCTYPE, f'<html lang="{LANGUAGE}">', head(title), tag("body", body), "</html>"]
    return "\n".join([*page, ""])


def head(title: str) -> str:
    """Give the head: the character set, the viewport, the title, and the only stylesheet."""
    return tag("head", CHARSET + VIEWPORT + tag("title", title) + tag("style", STYLESHEET))


def title_of(report: Report) -> str:
    """Name the page after the repository it is about."""
    return text(f"Audit of {report.provenance.repository}")


def run_header(report: Report) -> str:
    """Name the repository, what scanned it, and how much there is to read."""
    run = report.provenance
    tools = separated([text(f"syft {run.syft_version}"), text(f"trivy {run.trivy_version}")])
    named = tag("h1", title_of(report)) + tag("p", tools, "tools")
    return tag("header", named + database_line(run) + summary_line(report), "run")


def database_line(run) -> str:
    """Say when the advisory database was built, or shout that nothing said."""
    # A scan against no database finds nothing and exits 0. That is the one
    # failure a clean-looking report cannot be told from, so it is not quiet.
    if isinstance(run.database, AdvisoryDatabase):
        return tag("p", text(f"Advisory database built {run.database.built_at}"), "tools")
    return tag("p", text(f"NO ADVISORY DATABASE DATE: {run.database.reason}"), "alarm")


def summary_line(report: Report) -> str:
    """Say how much there is, and how much of it the sources argue about."""
    contested = len([one for one in report.findings if sources_disagree(one)])
    said = (
        f"{len(report.findings)} findings across {report.component_count} components. "
        f"{contested} carry sources that disagree."
    )
    return tag("p", text(said), "count")


def legend() -> str:
    """Say which of the two scales a reader is looking at, before they meet either."""
    return tag("p", text(LEGEND), "note")
