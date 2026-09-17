"""Every way the advisory database's date cannot be read answers None.

`db_snapshot_date` says in its own docstring that None is a normal answer which
degrades the audit -- the check does not run and coverage says so. Three of the
four ways of failing to read it did not answer None at all:

    metadata.json holding a list      -> AttributeError
    metadata.json holding a string    -> AttributeError
    metadata.json chmod 000           -> PermissionError

**This is on the audit path**, one line into `audit_run.advisory_inputs`, and
neither class is in `main.EXPECTED_FAILURES` -- so a cache directory somebody's
Trivy had left in an odd state crashed a run whose findings were already
correct, at the one place the code says it is allowed to shrug. The file is
written by a third-party tool into a directory a setting points at, which is
exactly the kind of input this project reads defensively everywhere else.

The document is guarded *and so is the member*: `UpdatedAt` holding a number is
the same fault one level down, and the pin would have carried it into
`findings.json` as a "date". That is the generalisation this round of fixes is
about -- a guard on the root and none on the field it is read for.

The database that is simply absent, and the date of one that is fine, are in
`test_trivy_runner.py` beside the rest of the runner's pure parts; the off
position is repeated here so "always None" cannot hold vacuously.

Nothing here runs Trivy or reads this machine's real cache: every metadata file
is written into `tmp_path`, and `default_cache_dir` is never reached because a
directory is always passed.
"""

import json
from pathlib import Path

import pytest

from advisory_fixtures import DB_UPDATED_AT
from deps.trivy_runner import db_snapshot_date
from locked_file import locked

# What a hand, an interrupted write or a different tool version leaves in the
# file. The first will not parse; the rest parse into something no `.get` works
# on.
UNREADABLE_METADATA = {
    "half written": '{"UpdatedAt": ',
    "a list": "[]",
    "a string": '"2026-02-01T06:00:00Z"',
    "a number": "7",
}
METADATA_IDS = list(UNREADABLE_METADATA)
METADATA_TEXTS = list(UNREADABLE_METADATA.values())

# The document is an object and the field is not a date. One level down, and
# the pin would have published whatever this held as `advisory_db_updated_at`.
NOT_A_DATE = {"a number": 7, "null": None, "a list": ["2026-02-01T06:00:00Z"],
              "an object": {"date": "2026-02-01T06:00:00Z"}}
DATE_IDS = list(NOT_A_DATE)
DATE_SHAPES = list(NOT_A_DATE.values())

# What a database this tool can read answers, so "None" is a measurement and not
# the only thing this function can say.
A_GOOD_DATE = DB_UPDATED_AT


def metadata_holding(cache_dir: Path, text: str) -> Path:
    """Write Trivy's database metadata where the runner looks for it, and return the path."""
    database = cache_dir / "db"
    database.mkdir(parents=True, exist_ok=True)
    path = database / "metadata.json"
    path.write_text(text, encoding="utf-8")
    return path


def answered(cache_dir: Path) -> str | None:
    """The date read from a cache, failing with the class of anything that escaped.

    The defect was never silence -- it was an exception of a class the audit
    path does not catch -- so the failure message names the one that got out.
    """
    try:
        return db_snapshot_date(cache_dir)
    except Exception as escaped:  # noqa: BLE001 - the class that escapes is the defect
        raise AssertionError(f"db_snapshot_date raised {type(escaped).__name__} "
                             f"instead of degrading: {escaped}") from escaped


# --- the file ---------------------------------------------------------------------

@pytest.mark.parametrize("text", METADATA_TEXTS, ids=METADATA_IDS)
def test_a_metadata_file_that_cannot_be_read_degrades_to_none(tmp_path,
                                                              text: str) -> None:
    """Two of these were `AttributeError` on the audit path, where None was promised."""
    metadata_holding(tmp_path, text)
    assert answered(tmp_path) is None


def test_a_metadata_file_nobody_can_open_degrades_to_none(tmp_path) -> None:
    """`OSError` is not `json.JSONDecodeError`, which is how it got out: `PermissionError`.

    `locked` attempts the read first and skips if it succeeded, so this cannot
    pass as root by reading a file it called unreadable.
    """
    locked(metadata_holding(tmp_path, f'{{"UpdatedAt": "{A_GOOD_DATE}"}}'))
    assert answered(tmp_path) is None


# --- and the field inside it -------------------------------------------------------

@pytest.mark.parametrize("shape", DATE_SHAPES, ids=DATE_IDS)
def test_an_updated_at_that_is_not_a_date_degrades_to_none(tmp_path,
                                                           shape: object) -> None:
    """The member, not just the document: a pin would have published this as a date."""
    metadata_holding(tmp_path, json.dumps({"UpdatedAt": shape}))
    assert answered(tmp_path) is None


def test_a_document_with_no_updated_at_at_all_degrades_to_none(tmp_path) -> None:
    """The absent field is the ordinary case the isinstance check must not change."""
    metadata_holding(tmp_path, '{"DownloadedAt": "2026-09-01T00:00:00Z"}')
    assert answered(tmp_path) is None


# --- the off position ---------------------------------------------------------------

def test_a_database_this_tool_can_read_still_answers_its_date(tmp_path) -> None:
    """Without it, a function that answered None to everything would pass every test above."""
    metadata_holding(tmp_path, f'{{"UpdatedAt": "{A_GOOD_DATE}"}}')
    assert answered(tmp_path) == A_GOOD_DATE
