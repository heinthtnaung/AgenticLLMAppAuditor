"""The entry point, and the exit code a pipeline reads.

Three outcomes, because a pipeline has to tell them apart:

| Code | Meaning |
|---|---|
| 0 | the audit ran and found nothing |
| 1 | the audit ran and found something |
| 2 | the audit could not run |

**Conflating the last two is how a broken scan passes a pipeline.** A missing
database, an absent scanner or a path that is not there would otherwise exit 0
beside a genuinely clean repository, and the build would go green on a scan that
never happened. `2` is also what `argparse` exits on a bad command line, so
every "could not run" leaves by the same door.
"""

import sys

from deps.scanner import ScannerFailed, ScannerUnavailable
from report.html_report import as_html
from report.json_report import as_json
from report.text_report import as_text

from cli.arguments import (
    HTML_FORMAT,
    JSON_FORMAT,
    PROGRAM,
    TEXT_FORMAT,
    Options,
    parse_arguments,
)
from cli.audit import run_audit
from cli.preflight import CannotRun, refuse_unrunnable

RENDERERS = {TEXT_FORMAT: as_text, JSON_FORMAT: as_json, HTML_FORMAT: as_html}

FOUND_NOTHING = 0
FOUND_SOMETHING = 1
COULD_NOT_RUN = 2


def main(argv: list[str] | None = None, out=None, error=None) -> int:
    """Run one audit and give the exit code that says which of the three happened."""
    out = sys.stdout if out is None else out
    error = sys.stderr if error is None else error
    try:
        options = parse_arguments(argv)
        report = audit(options, error)
    except (CannotRun, ScannerFailed, ScannerUnavailable, ValueError, OSError) as fault:
        error.write(f"{PROGRAM}: {fault}\n")
        return COULD_NOT_RUN
    out.write(rendered(report, options.report_format))
    return FOUND_SOMETHING if report.findings else FOUND_NOTHING


def audit(options: Options, error):
    """Check what a trustworthy report needs, then produce one."""
    # Progress goes to the error stream, so the audit record on stdout stays
    # pipeable and byte-identical whether or not anyone is watching.
    return run_audit(options, refuse_unrunnable(options.repository), error)


def rendered(report, report_format: str) -> str:
    """Render the record the way the command line asked for it."""
    renderer = RENDERERS.get(report_format)
    if renderer is None:
        named = ", ".join(RENDERERS)
        raise ValueError(f"{report_format!r} is no report format; this tool writes {named}")
    return renderer(report)


if __name__ == "__main__":
    sys.exit(main())
