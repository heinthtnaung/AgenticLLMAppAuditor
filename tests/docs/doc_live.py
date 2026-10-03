"""Running a page's own commands for real, and the failure a stale block is corrected from.

Each page's live test is a few lines over this, so every page is held the same
way. It shells out to Syft and Trivy over a repository fetched to
`fetched/vulnscout` and needs the pinned advisory database, none of which the
ordinary suite may depend on. Where any of those is absent it skips with the
reason, because **a failure here has to mean "the page is wrong" and nothing
else**, or it is a failure people learn to scroll past.

`doc_markers` finds the markers and refuses a page that lost one, `doc_runs`
reads each into the command that made it, `doc_answers` derives the answer file
it is handed, and `doc_drift` decides whether a block still reproduces and how
strictly it is entitled to ask. This file runs them and writes the failure.

The flag itself is declared in each live test and not here: `doc_gated` finds a
gated file by its `LIVE` line, and this file is not one.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cli.main import COULD_NOT_RUN
from cli.preflight import CannotRun, refuse_unrunnable
from deps.trivy_database import trivy_cache_directory
from doc_answers import answers_for
from doc_drift import Drift, drift_of, looks_elided
from doc_markers import MARKER_NAME, unmarked_note
from doc_pages import PROJECT_ROOT, Document, Page, read
from doc_runs import ELIDED_TOKEN, FETCHED, REPOSITORY, PrintedRun, arguments_of, printed_runs

SOURCE_PATH = "src"
SCAN_TIMEOUT_SECONDS = 600

WHOLE = "compared whole: every line, in the order and the place the page prints them"
SELECTION = f"{ELIDED_TOKEN}, so compared loosely: each line must appear, in order"


def fail_on_stale_blocks(document: Document, tmp_path: Path) -> None:
    """Run each command a page documents and fail with the new text of every line that drifted."""
    skip_without_a_scannable_corpus()
    link_the_corpus(tmp_path)
    page = read(document)
    reports = [report_on(one, page, tmp_path) for one in printed_runs(page)]
    stale = [report for report in reports if report]
    if stale:
        pytest.fail("\n\n".join([*stale, unmarked_note(page)]), pytrace=False)


def skip_without_a_scannable_corpus() -> None:
    """Skip where the repository, the scanners or the advisory database are not on this machine."""
    try:
        refuse_unrunnable(PROJECT_ROOT / REPOSITORY, trivy_cache_directory(os.environ))
    except CannotRun as fault:
        pytest.skip(f"{fault}; checking the docs needs {REPOSITORY}, Syft, Trivy and a database")


def link_the_corpus(tmp_path: Path) -> None:
    """Make the pages' relative repository path resolve from the directory each run starts in."""
    # Every run writes `reports/` where it starts; from the project root that
    # would overwrite the operator's own reports of vulnscout. A link, not a
    # copy, so the page's `fetched/vulnscout` is spelled and scanned unchanged.
    (tmp_path / FETCHED).symlink_to(PROJECT_ROOT / FETCHED, target_is_directory=True)


def report_on(run: PrintedRun, page: Page, tmp_path: Path) -> str:
    """Give the report of what one block no longer reproduces, or nothing if it does."""
    printed_now = output_of(run, page, tmp_path)
    gone = drift_of(run.printed, printed_now, run.elided)
    if not gone:
        return ""
    return describe(run, page, gone, printed_now)


def describe(run: PrintedRun, page: Page, gone: list[Drift], printed_now: list[str]) -> str:
    """Write the failure the page can be corrected from, with no second run by hand."""
    # The whole output goes in underneath. Re-running the tool to read the new
    # text is the work this check exists to remove, so it must not ask for it.
    pairs = [f"    page |{one.printed}\n     now |{one.current}" for one in gone]
    return "\n".join(
        [
            f"{page.document.path}:{run.line_number} is stale, in {len(gone)} of the "
            f"{len(run.printed)} lines it prints:",
            f"  <!-- {MARKER_NAME}: {run.directive} -->",
            f"  {SELECTION if run.elided else WHOLE}.",
            *how_to_elide(run, printed_now),
            "",
            *pairs,
            "",
            "What that command prints now, in full:",
            *(f"  | {line}" for line in printed_now),
        ]
    )


def how_to_elide(run: PrintedRun, printed_now: list[str]) -> list[str]:
    """Name the marker token, but only for a block whose every line does still appear in order."""
    if run.elided or not looks_elided(run.printed, printed_now):
        return []
    return [f"  Every line does appear, in order. If that is deliberate, mark it {ELIDED_TOKEN}."]


def output_of(run: PrintedRun, page: Page, tmp_path: Path) -> list[str]:
    """Run the command one block documents and give the lines it prints."""
    # Built by `arguments_of`, so what the check runs is what the marker tests
    # read. An answer file is written only for a run that is handed one, so a
    # page whose runs take none need not print one.
    answers = answer_path(run, page, tmp_path) if run.wants_answers else None
    return audited([sys.executable, "-m", "cli.main", *arguments_of(run, answers)], tmp_path)


def answer_path(run: PrintedRun, page: Page, tmp_path: Path) -> Path:
    """Write the answer file one run is handed: its page's own, with its marker's edits."""
    written = tmp_path / f"answers-{page.document.path.stem}-{run.line_number}.json"
    written.write_text(json.dumps(answers_for(run, page)), encoding="utf-8")
    return written


def audited(command: list[str], tmp_path: Path) -> list[str]:
    """Run one audit from `tmp_path` as `python -m cli.main`, the `main` behind `audit`."""
    finished = subprocess.run(
        command,
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / SOURCE_PATH)},
        capture_output=True,
        text=True,
        timeout=SCAN_TIMEOUT_SECONDS,
    )
    if finished.returncode == COULD_NOT_RUN:
        raise AssertionError(f"the page's own command could not run: {finished.stderr.strip()}")
    return [line.rstrip() for line in finished.stdout.splitlines()]
