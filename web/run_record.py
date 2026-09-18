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

# The one module in `src/` this file reaches for, and only for a pure function:
# `canonical_url` owns the rule for deciding whether two URLs name the same
# repository, and `pipeline._reused` already joins on it. Serving the answer is
# what keeps the page from re-deriving it -- a `.git` strip written again in
# JavaScript is a second owner of a join key, and a page that disagreed with
# the pipeline would show two groups for a repository the tool treated as one.
from repo_url import canonical_url

# Everything under `/api/` carries this. It went to 2 when the audit stopped
# blocking, and to 3 when a run gained a **required** `auditor`: an old page
# posts a body without one and the server answers 400, which is exactly the
# case this number exists to announce. The `comparison` key added alongside it
# would not have earned a bump on its own -- an old bundle ignores a key it does
# not know and renders the local arm, which is degraded rather than wrong.
# One constant, so seven bodies cannot claim seven versions.
REPLY_SCHEMA_VERSION = 3

# Free text on an endpoint with no authentication, so it is a claim and not an
# identity. Capped because it is the one operator-supplied string that is not a
# URL and it is rendered; control characters are refused for the same reason.
MAX_AUDITOR_LENGTH = 120

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


def auditor_refusals(name: str) -> list[str]:
    """Every reason this is not a usable auditor name, or an empty list.

    One spelling, used twice: the request turns it into a 400 and the record
    raises on it. Written twice it had already grown two different tests for
    "printable".
    """
    said = []
    if not name.strip():
        said.append("an audit records who asked for it; give an auditor name")
    elif len(name) > MAX_AUDITOR_LENGTH:
        said.append(f"the auditor name is {len(name)} characters, over the "
                    f"{MAX_AUDITOR_LENGTH} character cap")
    elif not name.isprintable():
        said.append("the auditor name must not contain control characters")
    return said


def now() -> str:
    """This moment, ISO 8601 UTC to the second."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today() -> str:
    """This date, ISO 8601 UTC. The day-resolution sibling of `now()`."""
    return datetime.now(timezone.utc).date().isoformat()


@dataclass(frozen=True)
class RunRecord:
    """One row: what was asked for, how far it got, and what it produced.

    Frozen, so a stage or a terminal status is a new record rather than a
    mutation -- the registry holds one of these per run and replaces it.
    """

    run_id: str
    repo_url: str
    # After `repo_url` rather than appended: it is required, so it carries no
    # default and cannot follow the defaulted fields below. The dataclass field
    # order is the store's column order, so this reorders the table -- and both
    # required fields sitting together reads correctly, since both are what was
    # asked for.
    auditor: str
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
    # Files a person attached as evidence. `[]` is a fact the endpoint can
    # always establish -- nothing was attached -- and never a gap, which is why
    # this one is not nullable.
    uploads: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Reject a record a reader could not act on."""
        refused = auditor_refusals(self.auditor)
        if refused:
            raise ValueError(refused[0])
        if self.status not in RUN_STATUSES:
            raise ValueError(f"unknown run status {self.status!r}; expected {RUN_STATUSES}")
        if (self.status == FAILED) != (self.error is not None):
            raise ValueError("a failed run carries an error and only a failed run does")
        if (self.status == RUNNING) != (self.finished_at is None):
            raise ValueError("a run has finished_at exactly when it is no longer running")


def started(repo_url: str, auditor: str, options: dict) -> RunRecord:
    """A run at the moment it was accepted: an id, a URL, a name, nothing else."""
    return RunRecord(run_id=uuid.uuid4().hex, repo_url=repo_url,
                     auditor=auditor, options=dict(options), started_at=now())


# The keys every single-run body carries. Named so a test can hold the set
# rather than trusting the serialiser, and so the store's columns and the wire's
# fields are checked against one list.
DURABLE_FIELDS = tuple(f.name for f in fields(RunRecord))

# Added at read time, never stored. For the two filesystem flags the reason is
# staleness: a stored flag about `artifacts/` becomes a lie the moment someone
# cleans it, and a stale claim that a run's evidence is present is exactly the
# shape of failure this tool exists to expose. For `canonical_repo_url` the
# reason is ownership: it is derived from a field on the same row by a function
# `src/` owns, so storing it would be a second copy that could disagree with
# the one the pipeline joins on.
# What actually answered, per arm. Read out of the stored envelope rather than
# stored again: `findings.json` already records it at `model_run`, in the same
# row, so a column would be a second copy of a fact already on disk -- the
# argument `HistoryStore.overwritten_since` makes for reading
# `$.comparison.artifacts_dir` the same way. It also means every row written
# before this existed answers without a migration.
#
# The names are here and the JSON paths are in `history_store.py`, which owns
# the SQL; that module builds its query from this tuple, so the two cannot fall
# out of order.
MODEL_FIELDS = ("local_model_identifier", "local_model_status",
                "cloud_model_identifier", "cloud_model_status")

# Added at read time, never stored. For the two filesystem flags the reason is
# staleness. For `canonical_repo_url` the reason is ownership. For the four
# model fields it is ownership too, of a different kind: the envelope is where
# the audit recorded them, and this row already carries the envelope.
COMPUTED_FIELDS = ("artifacts_present", "artifacts_current", "canonical_repo_url",
                   *MODEL_FIELDS)


def body(record: RunRecord, *, artifacts_present: bool, artifacts_current: bool,
         models: dict, result: dict | None = None) -> dict:
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
        # Computed here rather than passed in, unlike the two flags above: those
        # need a filesystem and a store query, so only the route can establish
        # them. This one needs the record alone, so computing it here makes a
        # caller unable to pass a wrong value.
        "canonical_repo_url": canonical_url(record.repo_url),
        # Checked rather than trusted: a caller passing three of the four, or a
        # fifth nobody registered, would otherwise serve a body whose keys
        # disagree with `COMPUTED_FIELDS` and every sweep that reads it.
        **_models(models),
        "result": result,
    }


def _models(models: dict) -> dict:
    """The four model fields, refusing any set of keys but exactly those."""
    if sorted(models) != sorted(MODEL_FIELDS):
        raise ValueError(
            f"expected exactly {MODEL_FIELDS}, got {tuple(sorted(models))}")
    return models


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
        "uploads": as_json(record.uploads),
        ENVELOPE: None if envelope is None else as_json(envelope),
    }


def from_columns(row) -> tuple["RunRecord", dict | None]:
    """One stored row back as a record, and the envelope beside it when there is one.

    Takes anything that maps column names to values, so the store can hand it a
    `sqlite3.Row` without this module importing sqlite3.
    """
    # Bare `json.loads`, and unlike a grading key that is right: these columns
    # were written by this module into a database `history_store` refuses to
    # open unless its own `user_version` matches, so the file is the tool's and
    # not a hand-edited one. A corrupt column here is a broken checkout, not a
    # state a person can reach by editing a file.
    held = dict(row)
    stored = held.pop(ENVELOPE, None)
    held["options"] = json.loads(held["options"])
    held["stages"] = json.loads(held["stages"])
    held["uploads"] = json.loads(held["uploads"])
    return RunRecord(**held), None if stored is None else json.loads(stored)
