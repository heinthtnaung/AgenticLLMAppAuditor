"""Shows the line a surface names, read from the audited tree.

**Read now, not proven to be what the audit read.** `fetch_repo` deletes `.git`
after pinning, so a fetched tree carries no history and
`check_tree_matches_pin` can only say so -- there is nothing to diff against. If
anything edited the tree after the audit, the line here is today's line. The
reply says which, and the page labels it, because presenting today's line as the
audited one is exactly the fact-shaped guess this project refuses elsewhere.

**The path comes from the client and is therefore not trusted.** The directory
is derived server-side from the run's own app name; the file is resolved inside
it and refused if it lands anywhere else. Artifacts are not served from here --
`downloads.py` owns those, by an allowlist this deliberately does not share,
because an audited tree is an open set of paths and an allowlist cannot describe
one.

**This GET can start a subprocess.** `check_tree_matches_pin` runs `git status`
when the tree carries `.git`, which a tool-fetched tree never does -- but a
locally audited clone does, and that is an unauthenticated read triggering a
process. It is bounded: `git` only, in the tree's own directory, output read and
never executed. Named here because "a GET only reads" is the assumption it
breaks.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException

import fetch_repo
from history_store import HistoryStore
from run_record import RunRecord
from run_routes import RUN_ID

# How many lines either side of the one a surface names. Enough to see what the
# line sits in, short enough that this is a quotation and not a file viewer.
CONTEXT_LINES = 6

# A tree this size is not source a person reads; refusing is cheaper than
# streaming a binary into a browser that asked for a line of code.
MAX_SOURCE_BYTES = 2 * 1024 * 1024

NO_SUCH_RUN = 404
NO_SOURCE = 404
REFUSED = 400


def register(app: FastAPI, store: HistoryStore) -> None:
    """Attach the source-window route to an application."""

    @app.get("/api/runs/{run_id}/source")
    def source(run_id: str, file: str, line: int) -> dict:
        """The lines around the one a surface names, as the tree holds them now."""
        record = _run(store, run_id)
        tree = _tree(record)
        held = _inside(tree, file)
        text = _read(held)
        lines = text.splitlines()
        if line < 1 or line > len(lines):
            raise HTTPException(
                status_code=NO_SOURCE,
                detail=f"{file} has {len(lines)} lines; this surface names line {line}. "
                       "The tree on disk is not the one that was audited.")
        first = max(1, line - CONTEXT_LINES)
        last = min(len(lines), line + CONTEXT_LINES)
        return {
            "file": file,
            "line": line,
            "first_line": first,
            "lines": lines[first - 1:last],
            # Always non-null for a tool-fetched tree: the clone drops `.git`
            # after pinning, so there is nothing left to check against. Said
            # here rather than assumed by the page.
            "unchecked": _pin_note(tree),
        }


def _pin_note(tree: Path) -> str:
    """Why this tree could not be checked against its pin, or "" when it matched.

    `check_tree_matches_pin` *raises* on the two cases it is most needed for --
    a drifted commit and a dirty tree -- and on a pin that cannot be read at
    all. Every one of those is a reason the lines below may not be the lines
    that were audited, which is exactly what this field exists to say. Letting
    them out as a 500 turned the honest channel into a crash.
    """
    try:
        return fetch_repo.check_tree_matches_pin(tree)
    except ValueError as cannot:
        return str(cannot)


def _run(store: HistoryStore, run_id: str) -> RunRecord:
    """The run this source belongs to, refusing an id no row carries."""
    found = store.get(run_id) if RUN_ID.match(run_id) else None
    if found is None:
        raise HTTPException(status_code=NO_SUCH_RUN, detail="no run has that id")
    return found[0]


def _tree(record: RunRecord) -> Path:
    """Where this run's audited source sits, refusing runs that have none.

    Derived from the app name the run recorded, never from anything a caller
    sent. A local-path audit is not served: the tool never recorded where that
    tree was, and guessing at a path on the server's disk is not something an
    unauthenticated endpoint should do.
    """
    if record.app is None:
        raise HTTPException(status_code=NO_SOURCE,
                            detail="this run resolved no app, so it has no tree to read")
    tree = fetch_repo.DOWNLOAD_ROOT / record.app
    if not tree.is_dir():
        raise HTTPException(
            status_code=NO_SOURCE,
            detail=f"{tree} is not on disk. Only a repository fetched by URL is kept "
                   "where this page can read it; a local-path audit is not.")
    return tree


def _inside(tree: Path, file: str) -> Path:
    """One file of the audited tree, refusing anything that resolves outside it."""
    asked = (tree / file).resolve()
    if tree.resolve() not in asked.parents or not asked.is_file():
        raise HTTPException(status_code=REFUSED,
                            detail=f"{file} is not a file of this run's audited tree")
    return asked


def _read(held: Path) -> str:
    """The file's text, refusing one too large, unopenable, or not text at all.

    `OSError` beside `UnicodeDecodeError`, and the `stat` inside the same
    window: an audited tree is somebody else's checkout, so a file this process
    cannot open is ordinary, and it was a 500 while a non-UTF-8 file next to it
    was a named 400. `baselines/static_rules.py` already catches both for the
    same kind of file.
    """
    try:
        if held.stat().st_size > MAX_SOURCE_BYTES:
            raise HTTPException(
                status_code=REFUSED,
                detail=f"{held.name} is over {MAX_SOURCE_BYTES} bytes; this shows source, "
                       "not whatever a repository happens to contain")
        return held.read_text(encoding="utf-8")
    except UnicodeDecodeError as not_text:
        raise HTTPException(
            status_code=REFUSED,
            detail=f"{held.name} is not UTF-8 text, so there is no line to show") from not_text
    except OSError as cannot_open:
        raise HTTPException(
            status_code=REFUSED,
            detail=f"{held.name} cannot be read: {cannot_open}") from cannot_open
