"""Which vexctl commands the emitter runs, and what the command line returns.

vexctl is replaced by a recorder here, so these tests check the sequence rather
than the document: one `create` for the first claim and one `add --in-place`
per claim after it. That sequence is the part this project decides -- the bytes
are the tool's, and the tests that read them live in test_emit_vex_vexctl.py.
"""

import json
import sys
from pathlib import Path

import pytest

from advisory_fixtures import advisory_document, advisory_finding
from artifacts.finding import SCHEMA_VERSION
from artifacts.sarif import DRIVER_NAME
from emit_vex import DOCUMENT_NAME, document_id, emit, main
from findings_fixtures import build_document
from sarif_fixtures import component_finding
from vex_fixtures import (
    ADD,
    CREATE,
    PINNED_EPOCH,
    PRODUCT,
    app_directory,
    reaching,
    record_runs,
    value_after,
)

SECOND_ADVISORY = "CVE-2024-0002"
THIRD_ADVISORY = "CVE-2024-0003"

NO_STATEMENT_MESSAGE = "no advisory findings"


def one_advisory_app(tmp_path: Path) -> Path:
    """An artifact directory whose findings imply exactly one statement."""
    return app_directory(tmp_path, advisory_document(advisory_finding()))


def three_advisory_app(tmp_path: Path) -> Path:
    """An artifact directory whose findings imply three statements."""
    document = advisory_document(advisory_finding(),
                                 advisory_finding(SECOND_ADVISORY),
                                 reaching("SearchTool", "app/tools.py", 40,
                                          advisory_id=THIRD_ADVISORY))
    return app_directory(tmp_path, document)


def verbs(calls: list[tuple[list[str], str]]) -> list[str]:
    """The vexctl subcommand of each recorded call, in the order they ran."""
    return [arguments[0] for arguments, _ in calls]


def test_the_first_statement_is_created_as_a_new_document(monkeypatch, tmp_path) -> None:
    """`create` authors the file, so it carries the author, the id and where to write."""
    calls = record_runs(monkeypatch)
    app_dir = one_advisory_app(tmp_path)
    emit(app_dir, PRODUCT)
    arguments = calls[0][0]
    assert arguments[0] == CREATE
    assert value_after(arguments, "--author") == DRIVER_NAME
    assert value_after(arguments, "--id") == document_id(PRODUCT, PINNED_EPOCH)
    assert value_after(arguments, "--file") == str(app_dir / DOCUMENT_NAME)


def test_one_statement_runs_create_and_nothing_else(monkeypatch, tmp_path) -> None:
    """A single claim needs no append, so a stray `add` would be a second version bump."""
    calls = record_runs(monkeypatch)
    emit(one_advisory_app(tmp_path), PRODUCT)
    assert verbs(calls) == [CREATE]


def test_the_later_statements_are_appended_in_place(monkeypatch, tmp_path) -> None:
    """N statements are one create and N-1 adds, each editing the file just written."""
    calls = record_runs(monkeypatch)
    app_dir = three_advisory_app(tmp_path)
    emit(app_dir, PRODUCT)
    assert verbs(calls) == [CREATE, ADD, ADD]
    for arguments, _ in calls[1:]:
        assert value_after(arguments, "--document") == str(app_dir / DOCUMENT_NAME)
        assert "--in-place" in arguments


def test_every_statement_names_a_different_advisory(monkeypatch, tmp_path) -> None:
    """Three findings are three claims, so no call may repeat another's vulnerability."""
    calls = record_runs(monkeypatch)
    emit(three_advisory_app(tmp_path), PRODUCT)
    named = [value_after(arguments, "--vuln") for arguments, _ in calls]
    assert sorted(named) == ["CVE-2024-0001", SECOND_ADVISORY, THIRD_ADVISORY]


def test_every_call_is_pinned_to_the_advisory_database_s_date(monkeypatch, tmp_path) -> None:
    """One instant for the whole document: a clock would time-order the statements."""
    calls = record_runs(monkeypatch)
    emit(three_advisory_app(tmp_path), PRODUCT)
    assert {epoch for _, epoch in calls} == {PINNED_EPOCH}


def test_the_emitted_path_is_returned_and_written(monkeypatch, tmp_path) -> None:
    """The command prints this path, so a reader must find a file at the end of it."""
    record_runs(monkeypatch)
    app_dir = one_advisory_app(tmp_path)
    assert emit(app_dir, PRODUCT) == app_dir / DOCUMENT_NAME
    assert (app_dir / DOCUMENT_NAME).is_file()


def test_no_advisory_finding_writes_no_document(monkeypatch, tmp_path) -> None:
    """An empty document would claim a clean bill the audit never established."""
    calls = record_runs(monkeypatch)
    app_dir = app_directory(tmp_path, advisory_document())
    assert emit(app_dir, PRODUCT) is None
    assert calls == []
    assert not (app_dir / DOCUMENT_NAME).exists()


def test_findings_that_carry_no_advisory_write_no_document(monkeypatch, tmp_path) -> None:
    """Trivy ran and the other checks found something: still nothing to state here."""
    calls = record_runs(monkeypatch)
    app_dir = app_directory(tmp_path, advisory_document(component_finding()))
    assert emit(app_dir, PRODUCT) is None
    assert calls == []
    assert not (app_dir / DOCUMENT_NAME).exists()


def test_a_missing_artifact_directory_is_refused(monkeypatch, tmp_path) -> None:
    """Named, so nobody reads a silent no-op as an app with nothing to state."""
    record_runs(monkeypatch)
    with pytest.raises(NotADirectoryError) as raised:
        emit(tmp_path / "never-audited", PRODUCT)
    assert "never-audited" in str(raised.value)


def run_main(monkeypatch: pytest.MonkeyPatch, app_dir: Path) -> int:
    """Run the command over one artifact directory, naming the product explicitly."""
    monkeypatch.setattr(sys, "argv", ["emit_vex.py", str(app_dir), "--product", PRODUCT])
    return main()


def test_the_command_reports_the_document_it_wrote(monkeypatch, tmp_path, capsys) -> None:
    """Exit 0 and the path on stdout, which is what a following step reads."""
    record_runs(monkeypatch)
    app_dir = one_advisory_app(tmp_path)
    assert run_main(monkeypatch, app_dir) == 0
    assert capsys.readouterr().out.strip() == f"wrote {app_dir / DOCUMENT_NAME}"


def test_the_command_succeeds_with_nothing_to_state(monkeypatch, tmp_path, capsys) -> None:
    """Not an error: no advisory finding is a real outcome, and it says so."""
    record_runs(monkeypatch)
    assert run_main(monkeypatch, app_directory(tmp_path, advisory_document())) == 0
    assert NO_STATEMENT_MESSAGE in capsys.readouterr().out


def test_an_unpinned_findings_document_fails_with_a_message(monkeypatch, tmp_path,
                                                            capsys) -> None:
    """Exit 1: an advisory finding with no database date behind it cannot be pinned."""
    record_runs(monkeypatch)
    unpinned = build_document([advisory_finding()])
    assert unpinned["coverage"]["advisory_db_updated_at"] is None
    assert run_main(monkeypatch, app_directory(tmp_path, unpinned)) == 1
    assert "no advisory data" in capsys.readouterr().err


# --- A stale contract is refused, not met with a KeyError ---------------------

def test_a_stale_findings_document_is_refused(monkeypatch, tmp_path) -> None:
    """The emitter reads findings.json off disk, so it needs report.py's guard.

    Measured before the guard existed: a schema-3 document reached
    `pinned_epoch` and raised `KeyError: 'advisory_db_updated_at'`, which
    `main` does not catch -- a traceback where a sentence belongs.
    """
    calls = record_runs(monkeypatch)
    app_dir = app_directory(tmp_path, advisory_document(advisory_finding()))
    stale = json.loads((app_dir / "findings.json").read_text(encoding="utf-8"))
    stale["schema_version"] = SCHEMA_VERSION - 1
    (app_dir / "findings.json").write_text(json.dumps(stale), encoding="utf-8")

    with pytest.raises(ValueError, match="schema_version"):
        emit(app_dir, PRODUCT)
    assert calls == [], "nothing may be authored from a document that was refused"


def test_the_command_reports_a_stale_document_as_an_exit_code(
        capsys, monkeypatch, tmp_path) -> None:
    """A regenerable artifact is the user's to fix, so it prints and exits 1."""
    app_dir = app_directory(tmp_path, advisory_document(advisory_finding()))
    stale = json.loads((app_dir / "findings.json").read_text(encoding="utf-8"))
    stale["schema_version"] = SCHEMA_VERSION - 1
    (app_dir / "findings.json").write_text(json.dumps(stale), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["emit_vex.py", str(app_dir), "--product", PRODUCT])

    assert main() == 1
    assert "schema_version" in capsys.readouterr().err
