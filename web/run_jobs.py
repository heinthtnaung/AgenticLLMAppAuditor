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

from artifacts_read import read_documents
from history_store import HistoryStore
import main
import run_record
from audit_request import AuditRequest
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

    def start(self, asked: AuditRequest) -> RunRecord:
        """Accept one audit and begin it. Raises `Busy` when one is already going.

        Two concurrent runs over one URL race between the "already fetched?"
        check and the clone, and two over one app overwrite `artifacts/<app>/`
        mid-write. Nothing in the CLI ever had to be reentrant.
        """
        record = run_record.started(asked.url.strip(), asdict(asked))
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
            produced = main.run(main.build_parser().parse_args(asked.to_argv()), note)
            self._finish(accepted, stages, started, produced)
        except REFUSALS as refusal:
            self._fail(accepted, stages, started, str(refusal))
        except Exception as unexpected:            # noqa: BLE001 - see below
            # Deliberately broad, and the only broad catch here. A worker thread
            # that dies with an exception leaves the run saying `running` for
            # ever and the guard held; a failed run naming the exception is the
            # honest outcome. The traceback still reaches the server's stderr.
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
            "app": produced["app"],
            "artifacts_dir": str(produced["artifacts"]),
            "seconds": produced["seconds"],
            "advisories_read": produced["advisories_read"],
            **documents,
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
