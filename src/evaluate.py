"""Scores every app that has a grading key, for one system, and writes its evaluation.

Separate from `main.py`, which audits one repository. `evaluation.json` spans a
whole run, and a whole-run artifact written by a per-app command is how a
partial run silently produces a complete-looking score.

It prints counts and never a rate. A reader who wants precision or recall
divides for themselves, which means holding the denominator and the
qualifications printed beside it — the same discipline the artifact enforces by
having no float field at all. The evidence-link shares the proposal asks for are
printed the same way: numerator, denominator and the apps they rest on.
"""

import argparse
import sys
from pathlib import Path

from evaluation.document import AGENTIC_AUDITOR, SCORED_SYSTEMS
from evaluation.harness import score_apps, write_evaluation
from grading_keys import KEYS_DIR, discover_graded_apps

DEFAULT_ARTIFACTS_DIR = Path("artifacts")

# Every failure a missing key or a missing artifact can raise, reported as one
# line rather than a traceback.
EXPECTED_FAILURES = (FileNotFoundError, NotADirectoryError, ValueError, RuntimeError)


def build_parser() -> argparse.ArgumentParser:
    """Describe the command line arguments."""
    parser = argparse.ArgumentParser(
        description="Score every app with a grading key, for one system, against that key.")
    parser.add_argument(
        "--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS_DIR,
        help=("the directory holding each system's artifacts, read as "
              f"<dir>/<system>/<app>/ (default: {DEFAULT_ARTIFACTS_DIR})"),
    )
    parser.add_argument(
        # A closed vocabulary, because this value becomes a directory name.
        "--system", choices=SCORED_SYSTEMS, default=AGENTIC_AUDITOR,
        help=f"which system's findings to score (default: {AGENTIC_AUDITOR})",
    )
    parser.add_argument(
        "--keys-dir", type=Path, default=KEYS_DIR,
        help=f"the directory holding <app>.ground_truth.json (default: {KEYS_DIR.name}/)")
    return parser


def app_lines(document: dict) -> list[str]:
    """Report each app's counts, with what bounds them on the same line."""
    lines = []
    for app in document["apps"]:
        false_positives = app["false_positives"]
        shown = "not measurable" if false_positives is None else false_positives
        lines.append(
            f"  {app['app']}: {app['true_positives']} of {app['key_finding_count']} matched, "
            f"{app['false_negatives']} missed, false positives {shown}")
        lines.append(f"    bounded by: {', '.join(app['qualifications']) or 'nothing'}")
    return lines


EVIDENCE_LABELS = (
    ("with_code_evidence", "code"),
    ("with_sbom_evidence", "SBOM/AIBOM"),
    ("with_vex_evidence", "VEX"),
)


def evidence_lines(document: dict) -> list[str]:
    """Report how many findings carry each kind of evidence link.

    Counts, not percentages, and not because the percentage is unwanted: this
    tool prints no rate anywhere outside `main.py`'s scan statistic, and two
    tests pin that. The denominator is on the line, so the division is one step
    for a reader who wants it -- holding the sample size, which is the point.
    """
    pooled = document["totals"]["evidence"]
    whole = pooled["findings_considered"]
    return [f"  {label} evidence: {pooled[key]} of {whole} findings "
            f"over {', '.join(pooled['apps_included']) or 'no app'}"
            for key, label in EVIDENCE_LABELS]


def totals_lines(document: dict) -> list[str]:
    """Report the pooled counts, naming the apps each one rests on."""
    totals = document["totals"]
    recall, precision = totals["recall"], totals["precision"]
    return [
        f"  recall pool: {recall['true_positives']} of {recall['key_finding_count']} "
        f"over {', '.join(recall['apps_included']) or 'no app'}",
        f"  precision pool: {precision['answered_finding_count']} of "
        f"{precision['produced_finding_count']} produced "
        f"over {', '.join(precision['apps_included']) or 'no app'}",
        f"  f1: {'reportable' if totals['f1_reportable'] else totals['f1_blocked_reason']}",
    ]


def run(args: argparse.Namespace) -> int:
    """Score every app with a key, for one system. Returns the process exit code.

    Every app found is scored or nothing is written. An app whose key is
    present and whose artifacts are not raises, rather than being dropped from
    the pool: `evaluation.json` has no field for who was skipped, so a quiet
    skip would ship as a complete score over fewer apps than a reader assumes.
    """
    apps = discover_graded_apps(args.keys_dir)
    artifacts_dir = args.artifacts_dir / args.system
    document = score_apps(list(apps), artifacts_dir, args.system, args.keys_dir)
    path = write_evaluation(document, artifacts_dir)

    print(f"scored {document['app_count']} apps as {args.system}, wrote {path}")
    for line in app_lines(document) + totals_lines(document) + evidence_lines(document):
        print(line)
    # No rate is printed, and none is a field: the division is the reader's,
    # and it needs the denominators above to be done honestly.
    return 0


def main() -> int:
    """Score every graded app. Returns the process exit code."""
    args = build_parser().parse_args()
    try:
        return run(args)
    except EXPECTED_FAILURES as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
