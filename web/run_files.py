"""Where one run's files live, and removing them when its row goes.

Split from `run_jobs.py` and `run_routes.py` because it is a third job: one
module decides *where* an audit writes, and the same rule decides what may be
deleted afterwards. A route that removes a directory tree wants that rule
beside the tree, not beside an HTTP status.

**Keyed on the run id, which is what makes removal safe at all.** Until
2026-09-18 every audit of one app wrote to `artifacts/<system>/<app>/`, shared
by every other audit of it -- so deleting "this run's files" would have taken
another run's evidence with them, and `HistoryStore.delete` says in its own
docstring that it removes a row and no files for exactly that reason. A tree
under `RUN_ARTIFACTS_ROOT / <run_id>` is owned by one run by construction:
there is no containment check here because there is no path to contain, only an
id this server generated and a route has already matched against `RUN_ID`.

It also covers **both arms**. A `--compare-models` run writes
`<run_id>/agentic_auditor/<app>/` and `<run_id>/cloud_auditor/<app>/`, and the
record's `artifacts_dir` names only the first -- so removing that column's
value would leave the hosted arm's files behind for ever.
"""

import shutil
from pathlib import Path

# Every run's own directory, under its own id. The `<system>/<app>` shape
# inside is the command line's, because `src/evaluate.py` and
# `evaluation.score_apps` both read that layout.
RUN_ARTIFACTS_ROOT = Path("artifacts") / "runs"


def run_artifacts(run_id: str, system: str) -> Path:
    """Where one run's named arm writes, under the run's own id."""
    return RUN_ARTIFACTS_ROOT / run_id / system


def run_keys(run_id: str) -> Path:
    """Where one run drafts its grading key, under the run's own id.

    Inside the run's tree rather than beside `grading_keys/drafts/`, so it is
    removed with the rest of the run's files when the row is forgotten -- and so
    nothing this server writes ever lands in the checkout's own key directory,
    where a human's corrected drafts live.
    """
    return RUN_ARTIFACTS_ROOT / run_id / "keys"


def own_tree(run_id: str) -> Path | None:
    """Everything one run wrote, both arms, or None when it wrote nothing here.

    None covers the two cases that are not an error: a run that failed before
    writing anything, and a run recorded before artifacts were keyed on the run
    at all -- whose files sit in a shared directory this must not touch.
    """
    directory = RUN_ARTIFACTS_ROOT / run_id
    return directory if directory.is_dir() else None


def remove(directory: Path) -> None:
    """Delete one run's own tree, and nothing above it.

    `ignore_errors` because this runs *after* the row is gone: the caller has
    already told the reader their run was forgotten, and a file this process
    cannot unlink is a leaked directory rather than a failed request. The row
    is the record; the files are evidence for it.
    """
    shutil.rmtree(directory, ignore_errors=True)


def remove_every_tree() -> None:
    """Delete every run's directory, for the wipe that deletes every row."""
    shutil.rmtree(RUN_ARTIFACTS_ROOT, ignore_errors=True)
