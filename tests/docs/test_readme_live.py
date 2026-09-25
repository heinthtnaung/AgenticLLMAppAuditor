"""The check that makes a stale README a test failure, skipped unless it is asked for.

`README.md` prints real CLI output beside the answer file that produced it.
Twice in one afternoon a rendering change left those blocks false and a person
caught it by hand; this is that person, made structural:

    README_LIVE_SCAN=1 python -m pytest tests/docs/test_readme_live.py

It is off by default because it shells out to Syft and Trivy over a repository
fetched to `fetched/vulnscout` and needs the pinned advisory database, none of
which the ordinary suite may depend on. Where any of those is absent it skips
with the reason, because **a failure here has to mean "the README is wrong" and
nothing else**, or it is a failure people learn to scroll past.

`readme_markers` finds the markers and refuses a page that lost one, `readme_runs`
reads each into the command that made it, `readme_answers` derives the answer
file it is handed, and `readme_drift` decides whether a block still reproduces
and how strictly it is entitled to ask. This file runs them and writes the
failure.

The markers themselves are guarded in `test_readme_markers.py`, which needs no
corpus and so is not gated: damage to a marker is caught by anyone running
`pytest`, and only the question of whether the printed output still reproduces
waits for a scan.
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
from readme_answers import answers_for
from readme_markers import PROJECT_ROOT, README_PATH, read_readme, unmarked_note
from readme_runs import (
    ELIDED_TOKEN, FETCHED, REPOSITORY, PrintedRun, arguments_of, printed_runs,
)
from readme_drift import Drift, drift_of, looks_elided

LIVE = "README_LIVE_SCAN"

pytestmark = pytest.mark.skipif(
    not os.environ.get(LIVE), reason=f"set {LIVE}=1 to run the README's own commands for real"
)

SOURCE_PATH = "src"
SCAN_TIMEOUT_SECONDS = 600

WHOLE = "compared whole: every line, in the order and the place the page prints them"
SELECTION = f"{ELIDED_TOKEN}, so compared loosely: each line must appear, in order"


def test_every_block_the_readme_prints_still_reproduces(tmp_path):
    """Run each documented command and fail with the new text of every line that drifted."""
    skip_without_a_scannable_corpus()
    link_the_corpus(tmp_path)
    page = read_readme()
    reports = [report_on(one, page, tmp_path) for one in printed_runs(page)]
    stale = [report for report in reports if report]
    if stale:
        pytest.fail("\n\n".join([*stale, unmarked_note(page)]), pytrace=False)


def skip_without_a_scannable_corpus() -> None:
    """Skip where the repository, the scanners or the advisory database are not on this machine."""
    try:
        refuse_unrunnable(PROJECT_ROOT / REPOSITORY, trivy_cache_directory(os.environ))
    except CannotRun as fault:
        pytest.skip(f"{fault}; checking the README needs {REPOSITORY}, Syft, Trivy and a database")


def link_the_corpus(tmp_path: Path) -> None:
    """Make the README's relative repository path resolve from the directory each run starts in."""
    # Every run writes `reports/` where it starts; from the project root that
    # would overwrite the operator's own reports of vulnscout. A link, not a
    # copy, so the page's `fetched/vulnscout` is spelled and scanned unchanged.
    (tmp_path / FETCHED).symlink_to(PROJECT_ROOT / FETCHED, target_is_directory=True)


def report_on(run: PrintedRun, page: str, tmp_path: Path) -> str:
    """Give the report of what one README block no longer reproduces, or nothing if it does."""
    printed_now = output_of(run, page, tmp_path)
    gone = drift_of(run.printed, printed_now, run.elided)
    if not gone:
        return ""
    return describe(run, gone, printed_now)


def describe(run: PrintedRun, gone: list[Drift], printed_now: list[str]) -> str:
    """Write the failure the README can be corrected from, with no second run by hand."""
    # The whole output goes in underneath. Re-running the tool to read the new
    # text is the work this check exists to remove, so it must not ask for it.
    pairs = [f"  README |{one.printed}\n     now |{one.current}" for one in gone]
    return "\n".join(
        [
            f"{README_PATH}:{run.line_number} is stale, in {len(gone)} of the "
            f"{len(run.printed)} lines it prints:",
            f"  <!-- readme-check: {run.directive} -->",
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


def output_of(run: PrintedRun, page: str, tmp_path: Path) -> list[str]:
    """Run the command one README block documents and give the lines it prints."""
    # Built by `arguments_of`, so what the check runs is what the marker tests read.
    arguments = arguments_of(run, answer_path(run, page, tmp_path))
    return audited([sys.executable, "-m", "cli.main", *arguments], tmp_path)


def answer_path(run: PrintedRun, page: str, tmp_path: Path) -> Path:
    """Write the answer file one run would be handed: the README's own, with its marker's edits."""
    written = tmp_path / f"answers-{run.line_number}.json"
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
        raise AssertionError(f"the README's own command could not run: {finished.stderr.strip()}")
    return [line.rstrip() for line in finished.stdout.splitlines()]
