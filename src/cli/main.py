"""The entry point, and the exit code a pipeline reads.

Four outcomes, because a pipeline has to tell them apart:

| Code | Meaning |
|---|---|
| 0 | the audit ran, found nothing, and read every manifest |
| 1 | the audit ran and found something |
| 2 | the audit could not run |
| 3 | the audit ran and found nothing, but could not read a manifest |

**Conflating `0` and `2` is how a broken scan passes a pipeline.** A missing
database, an absent scanner or a path that is not there would otherwise exit 0
beside a genuinely clean repository, and the build would go green on a scan that
never happened. `2` is also what `argparse` exits on a bad command line, so
every "could not run" leaves by the same door.

**Nothing found over a manifest nobody read is not a clean result either.** A
`package.json` with no lock file yields no package at all, so its dependencies
are never checked, and `0` there would put a green build on them. `3` keeps
that apart from `0`. A run with findings exits `1` whatever it could not read,
because the findings alone already stop the build.
"""

import os
import sys
from pathlib import Path
from typing import TextIO

from deps.manifests import ManifestsUnreadable
from deps.scanner import ScannerFailed, ScannerUnavailable
from deps.trivy_database import trivy_cache_directory
from report.html_report import as_html
from report.json_report import as_json
from report.record import Report
from report.text_report import as_text

from cli.arguments import (
    HTML_FORMAT,
    JSON_FORMAT,
    PROGRAM,
    TEXT_FORMAT,
    parse_arguments,
)
from cli.audit import run_audit
from cli.preflight import CannotRun, refuse_unrunnable
from cli.report_files import (
    REPORTS_DIRECTORY,
    CannotWriteReports,
    planned_reports,
    where_written,
    write_reports,
)

RENDERERS = {TEXT_FORMAT: as_text, JSON_FORMAT: as_json, HTML_FORMAT: as_html}
REFUSALS = (
    CannotRun, CannotWriteReports, ManifestsUnreadable, ScannerFailed, ScannerUnavailable,
    ValueError, OSError,
)

FOUND_NOTHING = 0
FOUND_SOMETHING = 1
COULD_NOT_RUN = 2
FOUND_NOTHING_BUT_UNREAD = 3


def main(
    argv: list[str] | None = None,
    out: TextIO | None = None,
    error: TextIO | None = None,
    reports: Path = REPORTS_DIRECTORY,
) -> int:
    """Run one audit, write its three reports, and give the code that says which outcome it was."""
    out = sys.stdout if out is None else out
    error = sys.stderr if error is None else error
    try:
        options = parse_arguments(argv)
        # Resolved once and handed to both halves: the database dated is the one scanned.
        database = refuse_unrunnable(options.repository, trivy_cache_directory(os.environ))
        paths = planned_reports(options.repository, reports)
        # Progress goes to the error stream, so the audit record on stdout stays
        # pipeable and byte-identical whether or not anyone is watching.
        report = run_audit(options, database, error)
    except REFUSALS as fault:
        return refused(fault, error)
    by_format = renderings(report)
    out.write(by_format[options.report_format])
    try:
        error.write(where_written(write_reports(by_format, paths)))
    except CannotWriteReports as fault:
        # The record is already on stdout, so the run is not lost; the exit
        # code still says it did not do everything it was asked to.
        return refused(fault, error)
    return outcome(report)


def outcome(report: Report) -> int:
    """Give the code for a run that ran: findings, nothing, or nothing over an unread manifest."""
    if report.findings:
        return FOUND_SOMETHING
    return FOUND_NOTHING_BUT_UNREAD if report.coverage.unread_manifests else FOUND_NOTHING


def renderings(report: Report) -> dict[str, str]:
    """Render the one record in every format, so no format needs the run again."""
    return {one: renderer(report) for one, renderer in RENDERERS.items()}


def refused(fault: Exception, error: TextIO) -> int:
    """Say why the run did not do what it was asked, and give the code for it."""
    error.write(f"{PROGRAM}: {fault}\n")
    return COULD_NOT_RUN


if __name__ == "__main__":
    sys.exit(main())
