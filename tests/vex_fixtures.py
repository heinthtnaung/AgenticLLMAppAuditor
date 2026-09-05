"""Shared VEX test data: the product under assessment, and vexctl held at arm's length.

Built on `advisory_fixtures`, which owns the findings document. This module adds
only what the emitter's tests need: an app to be the product, a way to anchor an
advisory finding on a second surface, an artifact directory on disk, and a
recorder that stands in for vexctl so no test starts a process to check which
commands would have run.
"""

from pathlib import Path

import pytest

import emit_vex
from advisory_fixtures import advisory_finding
from artifacts.finding import Finding
from artifacts.findings_document import findings_to_json
from cli_helpers import forbid_subprocesses

# The audited app, named as `product_iri` would name it: where it came from and
# the commit it was at. A VEX statement is about a product, so every test needs one.
PRODUCT = "https://example.com/an-audited-app@0123456789abcdef"

CREATE = "create"
ADD = "add"

# The epoch of the date `advisory_fixtures` pins its documents to
# (2026-02-01T06:00:00Z), written down rather than derived from the code.
PINNED_EPOCH = "1769925600"


def value_after(arguments: list[str], flag: str) -> str:
    """The value vexctl would read for one flag, found by position as vexctl finds it."""
    return arguments[arguments.index(flag) + 1]


def reaching(surface_name: str, file: str, line: int, **overrides) -> Finding:
    """An advisory finding anchored on one named surface at one file and line."""
    return advisory_finding(
        surface_id=f"{file}:{line}:TOOL_CALL:{surface_name}",
        surface_name=surface_name, file=file, line=line, **overrides)


def app_directory(tmp_path: Path, document: dict, name: str = "an-audited-app") -> Path:
    """Write one findings document into an artifact directory the emitter can read."""
    app_dir = tmp_path / name
    app_dir.mkdir()
    (app_dir / emit_vex.FINDINGS_NAME).write_text(findings_to_json(document), encoding="utf-8")
    return app_dir


def record_runs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[list[str], str]]:
    """Replace the vexctl call with a recorder, so which commands ran is checkable.

    The stand-in leaves the file `create` would have written, because the
    command prints the path it wrote and a reader will go looking for it. Real
    processes are banned alongside it, so a second launcher added to the
    emitter fails the test instead of quietly running.
    """
    forbid_subprocesses(monkeypatch)
    calls: list[tuple[list[str], str]] = []

    def fake_run(arguments: list[str], epoch: str) -> str:
        """Record one call and leave whatever file it claimed to write."""
        calls.append((list(arguments), epoch))
        if arguments[0] == CREATE:
            Path(value_after(arguments, "--file")).write_text("{}", encoding="utf-8")
        return ""

    monkeypatch.setattr(emit_vex, "_run", fake_run)
    return calls
