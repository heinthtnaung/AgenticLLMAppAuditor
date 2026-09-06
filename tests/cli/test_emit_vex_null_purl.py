"""What an unversioned component becomes on the vexctl command line.

The statement builder's half is in `tests/artifacts/test_vex_null_purl.py`;
this is where the consequence lands. A findings document holding an advisory
finding with no purl used to end `emit` in a `TypeError` from the sort. It now
authors a document -- and hands vexctl an **empty** `--subcomponents` value,
which is a claim about the product with no component named in it.

vexctl is replaced by a recorder, as in `test_emit_vex_command.py`, so this
starts no process and needs no tool installed. What the real tool does with an
empty identifier is not asserted here, because asserting it would mean running
it: what is asserted is that this project hands it one.
"""

from pathlib import Path

import pytest

from advisory_fixtures import ADVISORY_ID, ADVISORY_PURL, advisory_document
from emit_vex import DOCUMENT_NAME, emit
from vex_fixtures import (
    ADD,
    CREATE,
    PRODUCT,
    app_directory,
    reaching,
    record_runs,
    value_after,
)

# The value an unversioned component is stated under: no identifier at all.
NO_SUBCOMPONENT = ""

UNVERSIONED_COMPONENT = "an-unversioned-lib"

# One statement for the versioned component and one for the unversioned one,
# so the command sequence is a `create` followed by a single `add`.
EXPECTED_CALLS = 2


def mixed_app(tmp_path: Path) -> Path:
    """An artifact directory whose findings the SBOM could version only half of."""
    document = advisory_document(
        reaching("ShellTool", "app/agent.py", 12),
        reaching("SearchTool", "app/tools.py", 40, purl=None,
                 component_name=UNVERSIONED_COMPONENT))
    return app_directory(tmp_path, document)


def test_a_finding_with_no_purl_no_longer_ends_the_emitter_in_a_traceback(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The defect as a reader met it: one unversioned component and no document at all."""
    calls = record_runs(monkeypatch)
    written = emit(mixed_app(tmp_path), PRODUCT)
    assert written.name == DOCUMENT_NAME
    assert [arguments[0] for arguments, _ in calls] == [CREATE, ADD]
    assert len(calls) == EXPECTED_CALLS


def test_the_unversioned_component_reaches_vexctl_as_an_empty_identifier(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Stated, not fixed: the flag is passed with nothing in it.

    A row in `docs/TODO.md`'s Known defects table says the same thing, because
    a document naming no subcomponent restates the advisory rather than making
    this project's claim about which app reaches it.
    """
    calls = record_runs(monkeypatch)
    emit(mixed_app(tmp_path), PRODUCT)
    created = calls[0][0]
    assert value_after(created, "--subcomponents") == NO_SUBCOMPONENT
    assert value_after(created, "--vuln") == ADVISORY_ID


def test_the_versioned_component_is_still_stated_with_its_purl(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The control: the emitter's ordinary path is untouched by the empty key beside it."""
    calls = record_runs(monkeypatch)
    emit(mixed_app(tmp_path), PRODUCT)
    appended = calls[1][0]
    assert value_after(appended, "--subcomponents") == ADVISORY_PURL
    assert value_after(appended, "--product") == PRODUCT
