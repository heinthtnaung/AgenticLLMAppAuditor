"""Runs one audit on a background thread and records how far it got.

The audit takes seconds to minutes, so the request that asks for one returns a
run id immediately and the page polls. That is the whole reason this module
exists, and it brings one obligation with it: **the store is the only state.**
Every stage the audit announces is written there, so a poll reads what the
worker wrote rather than a second copy in memory that could disagree with it.

**Mutual exclusion lives here as one field, not as a held lock.** The lock is
taken and released inside a single call; `active_run_id` is what says an audit
is in flight. A lock acquired in the request thread and released in the worker
is legal and a trap: a worker that dies before its `finally` would pin every
later request at 409 until the server restarts.
"""

import subprocess
import threading
import time
from dataclasses import asdict, replace
from pathlib import Path

from artifacts_read import read_documents
from history_store import HistoryStore
import main
import run_files
import run_record
from audit_request import AuditRequest
from evaluation.document import AGENTIC_AUDITOR, CLOUD_AUDITOR
from run_record import FAILED, FINISHED, RunRecord

# What a user can fix, told as a failed run rather than a crash. Identical to
# `main.main`'s own catch: two front ends over one tool that refuse different
# things would be two different tools.
REFUSALS = (*main.EXPECTED_FAILURES, subprocess.SubprocessError)


class Busy(RuntimeError):
    """An audit is already running, and this wrapper runs one at a time."""


class Registry:
    """The one audit in flight, and the thread running it."""

    def __init__(self, store: HistoryStore) -> None:
        """Hold the store every run is written to."""
        self.store = store
        self._guard = threading.Lock()
        self._active: str | None = None

    def active_run_id(self) -> str | None:
        """The run in flight, or None. Read under the guard, like every writer."""
        with self._guard:
            return self._active

    def start(self, asked: AuditRequest, auditor: str) -> RunRecord:
        """Accept one audit and begin it. Raises `Busy` when one is already going.

        Two concurrent runs over one URL race between the "already fetched?"
        check and the clone, and two over one app overwrite `artifacts/<app>/`
        mid-write. Nothing in the CLI ever had to be reentrant.
        """
        # The name is a record field and not an option, so it is handed in
        # separately: options are what was audited and how, and replaying them
        # must not replay who ran it.
        record = run_record.started(asked.url.strip(), auditor.strip(),
                                    asdict(asked))
        with self._guard:
            if self._active is not None:
                raise Busy(
                    "an audit is already running; this wrapper runs one at a time "
                    "because two would race over the same fetch and artifacts")
            self._active = record.run_id
        # Between claiming the slot and the worker owning it, nothing may fail
        # silently: the worker's `finally` is what releases the slot, and it does
        # not exist yet. A store that cannot be written, or a thread that cannot
        # start, would otherwise wedge every later request at 409 until the
        # server restarts.
        try:
            self.store.save(record)
            threading.Thread(target=self._work, args=(asked, record),
                             daemon=True).start()
        except BaseException:
            with self._guard:
                self._active = None
            raise
        return record

    def _work(self, asked: AuditRequest, accepted: RunRecord) -> None:
        """Run the audit to a terminal status, whatever happens."""
        started = time.monotonic()
        stages: list[str] = []

        def note(name: str, _detail: str) -> None:
            """Record one boundary the audit announced, in the order it came."""
            stages.append(name)
            self.store.save(_with(accepted, stages=list(stages)))

        try:
            # Appended here rather than in `AuditRequest.to_argv`: that method
            # is the request's own meaning and a run id is not part of it --
            # its docstring says it never invents an option that was not asked
            # for, and `options` is stored as the dataclass so a re-run is
            # exact. A destination this wrapper chose is not a stored option.
            argv = asked.to_argv() + [
                "--artifacts-dir", str(_run_artifacts(accepted.run_id)),
                # Its own key directory too. Keys were addressed by app name, so
                # the first `--draft-key` run of an app wrote the key and every
                # later one hit `FileExistsError` and drafted nothing -- sharing
                # one file, which is what the history page was showing.
                "--drafts-dir", str(run_files.run_keys(accepted.run_id)),
            ]
            produced = main.run(main.build_parser().parse_args(argv), note)
            self._finish(accepted, stages, started, produced)
        except REFUSALS as refusal:
            self._fail(accepted, stages, started, str(refusal))
        except BaseException as unexpected:        # noqa: BLE001 - see below
            # Deliberately broad, and the only broad catch here. A worker thread
            # that dies leaves the run saying `running` for ever -- the `finally`
            # frees the slot, but nothing rewrites the row until the store is
            # next opened. A failed run naming the exception is the honest
            # outcome. The traceback still reaches the server's stderr.
            #
            # `BaseException`, not `Exception`, and that is not belt-and-braces:
            # `argparse` calls `sys.exit` on a value it cannot parse, and
            # `SystemExit` is not an `Exception`. A request whose model name
            # began with `-` wedged a row at `running` this way. The request is
            # refused before it gets here now; this is what stops the *next*
            # such escape being a row nobody can clear.
            self._fail(accepted, stages, started, f"{type(unexpected).__name__}: {unexpected}")
        finally:
            with self._guard:
                self._active = None

    def _finish(self, accepted: RunRecord, stages: list[str],
                started: float, produced: dict) -> None:
        """Store a finished run: its counts, its envelope, and where it wrote."""
        documents = read_documents(produced["artifacts"])
        envelope = {
            "schema_version": run_record.REPLY_SCHEMA_VERSION,
            **_arm(produced, documents),
            "comparison": _comparison(produced["comparison"]),
        }
        self.store.save(_with(
            accepted, status=FINISHED, finished_at=run_record.now(),
            seconds=time.monotonic() - started, stages=stages,
            app=produced["app"], artifacts_dir=str(produced["artifacts"]),
            # Read off each document's own count, never recounted here, and left
            # null when the document is absent -- a count with no document
            # behind it is what this project spends its design refusing.
            finding_count=_count(documents["findings"], "finding_count"),
            surface_count=_count(documents["surfaces"], "surface_count"),
        ), envelope)

    def _fail(self, accepted: RunRecord, stages: list[str],
              started: float, reason: str) -> None:
        """Store a failed run, carrying the sentence the command line would print."""
        self.store.save(_with(
            accepted, status=FAILED, finished_at=run_record.now(),
            seconds=time.monotonic() - started, stages=stages, error=reason))


def _arm(result: dict, documents: dict) -> dict:
    """One audited arm as the envelope's shape: four scalars and two documents."""
    return {
        "app": result["app"],
        "artifacts_dir": str(result["artifacts"]),
        "seconds": result["seconds"],
        "advisories_read": result["advisories_read"],
        **documents,
    }


def _comparison(cloud: dict | None) -> dict | None:
    """The hosted arm, or None when only one arm ran.

    `system` where the envelope carries `schema_version`: one constant repeated
    inside one reply is a disagreement waiting to be handled. **Both** names
    come from `evaluation.document` -- the arm's own and the one it is compared
    with -- so the page never has to spell either, which is the defect this
    project already has on record about the JSX rebuilding an id `src/` owns.
    None means one arm ran, never that a second arm found nothing.
    """
    if cloud is None:
        return None
    return {"system": CLOUD_AUDITOR, "compared_with": AGENTIC_AUDITOR,
            **_arm(cloud, read_documents(cloud["artifacts"]))}


def _run_artifacts(run_id: str) -> Path:
    """Where one run writes, under its own id so nothing else can overwrite it.

    **Until 2026-09-18 this wrapper passed no `--artifacts-dir` at all**, so
    every run took the command line's default and every audit of one app wrote
    to `artifacts/agentic_auditor/<app>/`: the history's files column read
    "overwritten" for every row but the newest, and those files were not
    recoverable. Nothing in `src/` changed to fix it -- the option already
    existed and this is a caller finally choosing a value for it.

    The system segment is `main.DEFAULT_ARTIFACTS_DIR`'s own name rather than a
    second spelling of `agentic_auditor`: the layout below this directory is the
    command line's, and one copy of that name is the most there may be.
    """
    return run_files.run_artifacts(run_id, main.DEFAULT_ARTIFACTS_DIR.name)


def _with(record: RunRecord, **changed) -> RunRecord:
    """The same run, further along. The record is frozen, so this is a new one.

    `dataclasses.replace` rather than reaching into `__dict__`: it re-runs
    `__post_init__`, so a combination the record refuses cannot be built here
    and stored anyway.
    """
    return replace(record, **changed)


def _count(document: dict | None, field: str) -> int | None:
    """A document's own count, or None when the audit wrote no such document."""
    return None if document is None else document.get(field)
