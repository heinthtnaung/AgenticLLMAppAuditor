"""The auditor's name is a fact about the request. It reaches no artifact, ever.

This is the test the field was allowed on the strength of, so it is the strong
one. The name is required by `POST /api/audit`, stored in the run record, shown
in the history list -- and none of that may reach a file under `artifacts/`,
because **an artifact that recorded who ran it would stop being byte-identical
between two people auditing one commit.** That guarantee is what lets this
project claim two audits of one tree produce the same bytes, and it is asserted
elsewhere in the suite against runs that know nothing about a web wrapper. A
name leaking into one file would make those claims quietly false.

Two halves, and the second is the one that matters:

- **The request the audit is built from has no field for a name at all.** It
  had one, and `options` is `asdict(asked)` -- so `options["auditor"]` carried a
  person into the values a re-run replays. Two tests below record the opposite
  of what they used to: the stored options name nobody, and the record beside
  them does.
- **After a real audit driven through the endpoint, no file the run wrote holds
  the name.** Every file under the artifacts directory is read as bytes and
  swept, JSON and rendered Markdown alike. The audit underneath is the real one:
  only the stages that would leave this process are replaced, which is what
  `real_audit_fixtures.py` stages and says.

The auditor used here is a name chosen to be unfindable by accident -- a word no
check, package, rule id or path could produce -- so a hit is a leak and never a
coincidence. Two guards below make the sweep non-vacuous: the run really carried
that name, and the sweep really read files.

What the synthetic tree costs: nothing in `mixed_app_fixtures` is oversized,
non-UTF-8, malformed or shaped in a way nobody foresaw, so this proves the name
does not leak through the artifacts that tree produces, not through every
artifact any tree could.

The whole file skips without the server packages: the name only exists on a
request, and with no fastapi there is nothing to post one to.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from dataclasses import fields                     # noqa: E402
from pathlib import Path                           # noqa: E402

from audit_request import AuditRequest             # noqa: E402
from main import build_parser                      # noqa: E402

from .api_stubs import audit_and_poll, client_over   # noqa: E402
from .real_audit_fixtures import URL, stub_every_outside_stage   # noqa: E402

# Chosen to be unfindable by accident: no check name, package, rule id, file
# path or piece of rendered prose can produce this string, so a hit in a written
# artifact is a leak rather than a coincidence. Deliberately not `audit_stub`'s
# `AUDITOR` -- that one is an ordinary name, and an ordinary name is exactly
# what a sweep cannot tell apart from the corpus it is sweeping.
UNMISTAKABLE_AUDITOR = "Zzyzx-Quokka-7391"

# The field name itself, looked for in two places a name must no longer be: the
# request's declaration, and the options a re-run is built from.
AUDITOR_FIELD = "auditor"

# What this staging really leaves on disk: five JSON documents, the SARIF, and
# the two rendered reports. Measured, not guessed -- the tree carries no
# dependency manifest and Syft is stubbed absent, so no bill of materials or
# mapping is written. A floor rather than an equality, because *which* files a
# run writes is `test_artifact_inventory.py`'s subject and this one is the
# sweep: what it needs is that the sweep read something, since an empty
# directory satisfies "the name is in no file" perfectly.
LEAST_FILES_A_RUN_WRITES = 8


def audit_naming_the_auditor(monkeypatch, tmp_path: Path) -> dict:
    """Run one real audit through the endpoint under the unmistakable name."""
    stub_every_outside_stage(monkeypatch, tmp_path)
    client, _ = client_over(tmp_path)
    record = audit_and_poll(client, URL, auditor=UNMISTAKABLE_AUDITOR)
    assert record["status"] == "finished", record["error"]
    return record


def written_files(tmp_path: Path, record: dict) -> list[Path]:
    """Every file the run left under the directory it says it wrote to."""
    directory = tmp_path / record["result"]["artifacts_dir"]
    return sorted(path for path in directory.rglob("*") if path.is_file())


# --- the command line the wrapper builds ---------------------------------------

def test_the_command_line_never_carries_the_name() -> None:
    """`to_argv` builds what `main.build_parser` parses, and that parser has no such option.

    The request cannot be *given* a name now, so this is stronger than it was:
    there is no field to leave out of the argv by accident.
    """
    argv = AuditRequest(url=URL, semantic_probe=True, draft_key=True,
                        compare_models=True, cloud_model="vendor/hosted").to_argv()
    assert not any(UNMISTAKABLE_AUDITOR in word for word in argv)
    assert AUDITOR_FIELD not in {field.name for field in fields(AuditRequest)}


def test_the_parsed_command_line_has_nowhere_to_put_the_name() -> None:
    """The other direction: no option the parser owns is a place a name could travel in."""
    parsed = build_parser().parse_args(AuditRequest(url=URL).to_argv())
    assert not any(UNMISTAKABLE_AUDITOR in str(value) for value in vars(parsed).values())
    assert AUDITOR_FIELD not in vars(parsed)


# --- the files a real run wrote -------------------------------------------------

def test_no_file_the_audit_wrote_holds_the_auditors_name(monkeypatch, tmp_path) -> None:
    """The guarantee the field was allowed on: artifacts stay byte-identical between people."""
    record = audit_naming_the_auditor(monkeypatch, tmp_path)
    holding = [path.name for path in written_files(tmp_path, record)
               if UNMISTAKABLE_AUDITOR in path.read_bytes().decode("utf-8", "replace")]
    assert holding == []


def test_no_filename_the_audit_wrote_holds_the_auditors_name(monkeypatch,
                                                             tmp_path) -> None:
    """A name in a path is a leak the content sweep above would read straight past."""
    record = audit_naming_the_auditor(monkeypatch, tmp_path)
    assert not any(UNMISTAKABLE_AUDITOR in str(path)
                   for path in written_files(tmp_path, record))


# --- guards, so the sweep is about the name and not about an empty directory ----

def test_the_run_really_carried_that_name(monkeypatch, tmp_path) -> None:
    """Non-vacuity: a request the server never saw would leak nothing either."""
    record = audit_naming_the_auditor(monkeypatch, tmp_path)
    assert record["auditor"] == UNMISTAKABLE_AUDITOR


def test_the_options_a_re_run_would_replay_name_nobody(monkeypatch, tmp_path) -> None:
    """This test asserted the opposite, and it was right to pin what it found.

    `options["auditor"]` held the name, padding and all, while the record held
    the stripped one -- one answer written twice, already disagreeing. The field
    came off `AuditRequest`, so `options` is now what `docs/SCHEMAS.md` says it
    is: exactly the audit's own fields, replayable by anyone.
    """
    record = audit_naming_the_auditor(monkeypatch, tmp_path)
    assert AUDITOR_FIELD not in record["options"]
    assert not any(UNMISTAKABLE_AUDITOR in str(value)
                   for value in record["options"].values())


def test_the_sweep_really_read_the_files_the_audit_wrote(monkeypatch, tmp_path) -> None:
    """Non-vacuity: an empty directory satisfies "the name is in no file" perfectly."""
    record = audit_naming_the_auditor(monkeypatch, tmp_path)
    written = written_files(tmp_path, record)
    assert len(written) >= LEAST_FILES_A_RUN_WRITES
    assert all(path.read_bytes() for path in written)


def test_the_sweep_would_see_the_name_if_a_file_held_it(monkeypatch, tmp_path) -> None:
    """Non-vacuity of the comparison itself: plant the name and the sweep reports that file."""
    record = audit_naming_the_auditor(monkeypatch, tmp_path)
    planted = written_files(tmp_path, record)[0]
    planted.write_text(f"leaked by {UNMISTAKABLE_AUDITOR}\n", encoding="utf-8")
    holding = [path.name for path in written_files(tmp_path, record)
               if UNMISTAKABLE_AUDITOR in path.read_bytes().decode("utf-8", "replace")]
    assert holding == [planted.name]
