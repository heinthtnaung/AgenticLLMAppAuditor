"""One audit job: its vocabulary, its shape on the wire, and its timestamps.

FastAPI-free on purpose, like `audit_request.py` beside it, so the record and
its closed vocabulary can be tested on a clean checkout where the server
packages were never installed -- and so neither the router nor the store owns
the vocabulary they both have to agree about.

**`null` is not zero, anywhere in here.** `finding_count` is null when no
`findings.json` stands behind it, and that is a different fact from an audit
that looked and found none. The distinction is this project's whole subject, so
the record carries it as a type rather than as a convention a reader must know.
"""

import json
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone

# Everything under `/api/` carries this. It went to 2 when the audit stopped
# blocking: the result envelope's seven keys did not change, the protocol around
# them did, and the number exists to tell a separately-built page which protocol
# it is talking to. One constant, so three bodies cannot claim three versions.
REPLY_SCHEMA_VERSION = 2

RUNNING = "running"
FINISHED = "finished"
FAILED = "failed"

# Closed, and three values rather than four. `cancelled` lands in the change
# that ships a cancel endpoint: a value no producer can write is a branch every
# reader carries for ever against a case that cannot happen, which is why
# `artifacts/vex.py` refuses `not_affected` rather than allowing it.
RUN_STATUSES = (RUNNING, FINISHED, FAILED)

# What a run that stopped with its server says. A row left saying `running`
# would spin in the history view for ever -- a gap rendered as work in progress.
INTERRUPTED = "the server stopped before this run finished"


def now() -> str:
    """This moment, ISO 8601 UTC to the second."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class RunRecord:
    """One row: what was asked for, how far it got, and what it produced.

    Frozen, so a stage or a terminal status is a new record rather than a
    mutation -- the registry holds one of these per run and replaces it.
    """

    run_id: str
    repo_url: str
    options: dict
    started_at: str
    status: str = RUNNING
    finished_at: str | None = None
    seconds: float | None = None
    stages: list[str] = field(default_factory=list)
    app: str | None = None
    artifacts_dir: str | None = None
    finding_count: int | None = None
    surface_count: int | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        """Reject a record a reader could not act on."""
        if self.status not in RUN_STATUSES:
            raise ValueError(f"unknown run status {self.status!r}; expected {RUN_STATUSES}")
        if (self.status == FAILED) != (self.error is not None):
            raise ValueError("a failed run carries an error and only a failed run does")
        if (self.status == RUNNING) != (self.finished_at is None):
            raise ValueError("a run has finished_at exactly when it is no longer running")


def started(repo_url: str, options: dict) -> RunRecord:
    """A run at the moment it was accepted: an id, a URL, and nothing else known."""
    return RunRecord(run_id=uuid.uuid4().hex, repo_url=repo_url,
                     options=dict(options), started_at=now())


# The keys every single-run body carries. Named so a test can hold the set
# rather than trusting the serialiser, and so the store's columns and the wire's
# fields are checked against one list.
DURABLE_FIELDS = tuple(f.name for f in fields(RunRecord))

# Added at read time, never stored. A stored flag about the filesystem becomes a
# lie the moment someone cleans `artifacts/`, and a stale claim that a run's
# evidence is present is exactly the shape of failure this tool exists to expose.
COMPUTED_FIELDS = ("artifacts_present", "artifacts_current")


def body(record: RunRecord, *, artifacts_present: bool, artifacts_current: bool,
         result: dict | None = None) -> dict:
    """The record as one API body, with what only a reader can know added.

    `result` is the audit's own envelope and is present exactly when the run
    finished. The 202 that accepts a run answers with this same shape, so a page
    needs one parser rather than one per endpoint.
    """
    return {
        "schema_version": REPLY_SCHEMA_VERSION,
        **asdict(record),
        "artifacts_present": artifacts_present,
        "artifacts_current": artifacts_current,
        "result": result,
    }


def summary(full_body: dict) -> dict:
    """One history-list entry: the body without the result it embeds.

    `result` holds two whole artifacts; fifty of them in one reply is not a
    view. Derived from the body rather than built separately, so the list and
    the detail cannot describe a run differently.
    """
    return {key: value for key, value in full_body.items()
            if key not in ("result", "schema_version")}


def as_json(value: dict | list) -> str:
    """Stable JSON for a text column: sorted, so the stored bytes do not vary."""
    return json.dumps(value, sort_keys=True)


# The one stored column that is not a field of the record: the whole result
# envelope, kept so a finished run stays readable after `artifacts/` is cleaned.
ENVELOPE = "envelope"


def to_columns(record: RunRecord, envelope: dict | None) -> dict:
    """One record as storable columns: the two structured fields become JSON.

    Here rather than in the store because it is serialisation, not SQL -- the
    store's job is the database, and this is what a record looks like flattened.
    """
    return {
        **{name: getattr(record, name) for name in DURABLE_FIELDS},
        "options": as_json(record.options),
        "stages": as_json(record.stages),
        ENVELOPE: None if envelope is None else as_json(envelope),
    }


def from_columns(row) -> tuple["RunRecord", dict | None]:
    """One stored row back as a record, and the envelope beside it when there is one.

    Takes anything that maps column names to values, so the store can hand it a
    `sqlite3.Row` without this module importing sqlite3.
    """
    held = dict(row)
    stored = held.pop(ENVELOPE, None)
    held["options"] = json.loads(held["options"])
    held["stages"] = json.loads(held["stages"])
    return RunRecord(**held), None if stored is None else json.loads(stored)
