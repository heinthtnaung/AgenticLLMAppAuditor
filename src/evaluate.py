"""Scores every corpus fixture for one system and writes its evaluation.

Separate from `main.py`, which audits one repository. `evaluation.json` spans a
whole run, and a whole-run artifact written by a per-app command is how a
partial run silently produces a complete-looking score.

It prints counts and never a rate. A reader who wants precision or recall
divides for themselves, which means holding the denominator and the
qualifications printed beside it — the same discipline the artifact enforces by
having no float field at all.
"""

import argparse
import sys
from pathlib import Path

from corpus_paths import DOWNLOAD_HINT, app_is_present, discover_corpus_apps
from evaluation.document import AGENTIC_AUDITOR, SCORED_SYSTEMS
from evaluation.harness import score_apps, write_evaluation

DEFAULT_ARTIFACTS_DIR = Path("artifacts")

# Every failure a bad corpus or a missing artifact can raise, reported as one
# line rather than a traceback.
EXPECTED_FAILURES = (FileNotFoundError, NotADirectoryError, ValueError, RuntimeError)


def build_parser() -> argparse.ArgumentParser:
    """Describe the command line arguments."""
    parser = argparse.ArgumentParser(
        description="Score the corpus fixtures for one system against their grading keys.")
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
    return parser


def check_downloaded(apps: tuple[str, ...]) -> None:
    """Refuse to score a fixture whose source was never fetched.

    Distinct from a missing artifact: "run the auditor first" is the wrong
    instruction for an app that is not on disk to audit.
    """
    absent = [app for app in apps if not app_is_present(app)]
    if absent:
        raise FileNotFoundError(
            f"cannot score {', '.join(absent)}: {DOWNLOAD_HINT}")


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


def totals_lines(document: dict) -> list[str]:
    """Report the pooled counts, naming the apps each one rests on."""
    totals = document["totals"]
    recall, precision = totals["recall"], totals["precision"]
    return [
        f"  recall pool: {recall['true_positives']} of {recall['key_finding_count']} "
        f"over {', '.join(recall['apps_included']) or 'no app'}",
        f"  precision pool: {precision['true_positives']} of "
        f"{precision['produced_finding_count']} produced "
        f"over {', '.join(precision['apps_included']) or 'no app'}",
        f"  f1: {'reportable' if totals['f1_reportable'] else totals['f1_blocked_reason']}",
    ]


def run(args: argparse.Namespace) -> int:
    """Score every fixture for one system. Returns the process exit code."""
    apps = discover_corpus_apps()
    check_downloaded(apps)
    artifacts_dir = args.artifacts_dir / args.system
    document = score_apps(list(apps), artifacts_dir, args.system)
    path = write_evaluation(document, artifacts_dir)

    print(f"scored {document['app_count']} apps as {args.system}, wrote {path}")
    for line in app_lines(document) + totals_lines(document):
        print(line)
    # No rate is printed, and none is a field: the division is the reader's,
    # and it needs the denominators above to be done honestly.
    return 0


def main() -> int:
    """Score the corpus. Returns the process exit code."""
    args = build_parser().parse_args()
    try:
        return run(args)
    except EXPECTED_FAILURES as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
