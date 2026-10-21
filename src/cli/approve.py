"""Recording a decision on a report that already ran, without running the audit again.

A council run can take over an hour and does not reproduce, so a reader who has
read the report should not have to run it again to approve it. This reads the saved
JSON back into the record it was rendered from, re-renders all three reports, and
writes the decision in only where each re-render matches the saved file byte for byte.

**What that check catches, and what it does not.** It refuses a report whose three
files disagree with each other, and one this version of the tool would render
differently -- a different scoring-rules version, or any edit to a value the text or
HTML page shows. It does **not** catch an edit confined to the JSON, to a field the
other two pages never render (an advisory's summary, a fixed version, a seed): the
JSON re-renders to itself and the other two are untouched, so a consistent edit
there survives. The JSON is the fuller record, so it carries fields the summaries do
not, and the check is a cross-rendering agreement, not a signature.

**Only the approval changes.** Everything else -- findings, scores, council,
provenance -- is the run's, read back and written out unchanged. The approval is
the answers file's, marked as attached after the run so the record stays honest
that it was not part of it.
"""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from cli.arguments import HTML_FORMAT, JSON_FORMAT, TEXT_FORMAT
from cli.organisation_run import read_approval
from cli.report_files import ENCODING, SUFFIXES, refuse_unwritable, where_written, write_reports
from organisation.approval import Approval
from report.absences import APPROVAL_RECORD
from report.html_report import as_html
from report.json_report import as_json
from report.load_report import report_from_json
from report.record import Report
from report.text_report import as_text
from scoring.version import SCORING_RULES_VERSION

RENDERERS: dict[str, Callable[[Report], str]] = {
    TEXT_FORMAT: as_text, JSON_FORMAT: as_json, HTML_FORMAT: as_html,
}
SCORING_RULES_KEY = "scoring_rules_version"
NO_APPROVAL_IN_ANSWERS = "carries no approval block, so there is no decision to record"
ALREADY_APPROVED = "already carries an approval; pass --replace-approval to replace it"


class CannotApprove(ValueError):
    """An approval that cannot be recorded on this report, said with why and on which file."""


def record_approval(report_json: Path, answers: Path, replace_approval: bool) -> dict[str, str]:
    """Read the saved report, prove it reproduces, and give the three reports with the decision."""
    document = read_document(report_json)
    refuse_wrong_rules(document, report_json)
    record = load_record(document, report_json)
    refuse_already_approved(record, replace_approval, report_json)
    reproduces_saved(record, report_json)
    # Before rendering, so a read-only .html does not leave the .txt and .json rewritten.
    refuse_unwritable_siblings(report_json)
    approved = with_approval(record, decision_from(answers))
    return {name: render(approved) for name, render in RENDERERS.items()}


def refuse_unwritable_siblings(report_json: Path) -> None:
    """Refuse before any write if one of the three report files cannot be replaced."""
    for path in report_siblings(report_json).values():
        refuse_unwritable(path)


def with_approval(record: Report, approval: Approval) -> Report:
    """Record the decision and drop the approval absence, the one thing a decision changes."""
    kept = tuple(one for one in record.not_assessed if one.what != APPROVAL_RECORD)
    return replace(record, approval=approval, not_assessed=kept)


def write_approved(renderings: dict[str, str], report_json: Path) -> str:
    """Write the three reports back beside the JSON, and say where they went, as a run does."""
    written = write_reports(renderings, report_siblings(report_json))
    return where_written(written)


def report_siblings(report_json: Path) -> dict[str, Path]:
    """Name the three report files beside the JSON, which are the ones this rewrites."""
    return {name: report_json.with_suffix(suffix) for name, suffix in SUFFIXES.items()}


def read_document(report_json: Path) -> dict[str, Any]:
    """Read the saved report JSON, refusing one that is absent or is not readable JSON."""
    try:
        document = json.loads(report_json.read_text(encoding=ENCODING))
    except OSError as fault:
        raise CannotApprove(f"no report to approve at {str(report_json)!r}: {fault}") from fault
    except ValueError as fault:
        raise CannotApprove(f"{str(report_json)!r} is not readable JSON: {fault}") from fault
    if not isinstance(document, dict):
        raise CannotApprove(f"{str(report_json)!r} must hold the JSON object of a report")
    return document


def refuse_wrong_rules(document: dict[str, Any], report_json: Path) -> None:
    """Refuse a report scored by other rules than this code's, which could not re-render alike."""
    run = document.get("run")
    version = run.get(SCORING_RULES_KEY) if isinstance(run, dict) else None
    if version is not None and version != SCORING_RULES_VERSION:
        raise CannotApprove(
            f"{str(report_json)!r} was scored by rules {version!r}, not this tool's "
            f"{SCORING_RULES_VERSION!r}; approve it with the version that wrote it"
        )


def load_record(document: dict[str, Any], report_json: Path) -> Report:
    """Read the whole record back, naming the file and the fault for a JSON this cannot read."""
    # A report this tool did not write can be malformed in ways the loader's own checks
    # do not reach -- a wrong type cast, a missing key read without `require` -- so the
    # faults those raise are caught here too and named, never left as a bare traceback.
    try:
        return report_from_json(document, str(report_json))
    except (ValueError, KeyError, TypeError, AttributeError) as fault:
        said = f"{str(report_json)!r} is not a report this tool can read: {fault}"
        raise CannotApprove(said) from fault


def refuse_already_approved(record: Report, replace_approval: bool, report_json: Path) -> None:
    """Refuse to overwrite a decision a report already carries, unless replacing was asked for."""
    if isinstance(record.approval, Approval) and not replace_approval:
        raise CannotApprove(f"{str(report_json)!r} {ALREADY_APPROVED}")


def reproduces_saved(record: Report, report_json: Path) -> None:
    """Refuse unless the record re-renders to every saved file byte for byte, naming a mismatch."""
    for name, suffix in SUFFIXES.items():
        compare_saved(record, report_json.with_suffix(suffix), name)


def compare_saved(record: Report, path: Path, name: str) -> None:
    """Refuse one saved file the record does not reproduce, which is an edit or another version."""
    try:
        saved = path.read_text(encoding=ENCODING)
    except OSError as fault:
        raise CannotApprove(f"cannot read the saved report {str(path)!r}: {fault}") from fault
    if saved != RENDERERS[name](record):
        raise CannotApprove(
            f"{str(path)!r} is not what this tool would write for this record; "
            "it was edited by hand or written by another version, so it is not approved"
        )


def decision_from(answers: Path) -> Approval:
    """Read the decision from the answers file, refusing none, marked as attached after the run."""
    # `read_approval` names only the bad value ("'maybe' is not a decision"); name the file
    # too, as the other refusals do. The normal run reads it without this wrapping, so its
    # message is unchanged.
    try:
        outcome = read_approval(answers)
    except ValueError as fault:
        raise CannotApprove(f"{str(answers)!r}: {fault}") from fault
    if not isinstance(outcome, Approval):
        raise CannotApprove(f"{str(answers)!r} {NO_APPROVAL_IN_ANSWERS}")
    return replace(outcome, attached_after_run=True)
