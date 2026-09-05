"""Shared setup for the one-command pipeline's tests: every stage stubbed.

`pipeline.py` composes stages that each have test files of their own, so the
tests here replace each stage at the seam the pipeline calls it through:
`fetch` on the pipeline's own imported name, `emit` and `is_available` on
`emit_vex`, `export_all` on `export_reports`, `format_report` on `ai_report`.
Nothing in this module clones, launches a process, calls a model, or writes
outside the tmp_path a test hands it.
"""

from pathlib import Path

import pytest

import ai_report
import emit_vex
import export_reports
import fetch_repo
import pipeline
from fetch_helpers import COMMIT, COMMIT_DATE, NAME, SOURCE_FILE, SOURCE_TEXT, URL


def point_download_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Send the pipeline's reuse lookup to a root under tmp_path, never the real one."""
    root = tmp_path / "fetched"
    root.mkdir(exist_ok=True)
    monkeypatch.setattr(pipeline, "DOWNLOAD_ROOT", root)
    return root


def record_fetch(monkeypatch: pytest.MonkeyPatch, result: Path | None = None,
                 error: Exception | None = None) -> list[str]:
    """Replace the fetch stage with a recorder that returns a path or raises."""
    calls: list[str] = []

    def fake_fetch(url: str) -> Path:
        """Record the URL the pipeline handed over, then answer or refuse."""
        calls.append(url)
        if error is not None:
            raise error
        return result

    monkeypatch.setattr(pipeline, "fetch", fake_fetch)
    return calls


def plant_tree(root: Path, name: str = NAME) -> Path:
    """Leave the source tree a prior fetch would have left under the root."""
    tree = root / name
    tree.mkdir(parents=True)
    (tree / SOURCE_FILE).write_text(SOURCE_TEXT, encoding="utf-8")
    return tree


def write_pin(root: Path, url: str = URL, name: str = NAME) -> Path:
    """Leave the pin a prior fetch of `url` would have written beside its tree."""
    return fetch_repo.write_manifest(
        root, fetch_repo.manifest(name, url, COMMIT, COMMIT_DATE))


def record_publish(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Path, bool]]:
    """Replace the publish stage with a recorder of (app_artifacts, advisories_read)."""
    calls: list[tuple[Path, bool]] = []

    def fake_publish(app_artifacts: Path, advisories_read: bool) -> None:
        """Record what the pipeline asked to publish, and publish nothing."""
        calls.append((app_artifacts, advisories_read))

    monkeypatch.setattr(pipeline, "publish", fake_publish)
    return calls


def stub_vex(monkeypatch: pytest.MonkeyPatch, available: bool = True,
             written: Path | None = None,
             error: Exception | None = None) -> list[Path]:
    """Make vexctl look installed (or not), and record what emit is asked to write."""
    calls: list[Path] = []

    def fake_emit(app_artifacts: Path) -> Path | None:
        """Record the artifact directory, then answer as vexctl would or fail."""
        calls.append(app_artifacts)
        if error is not None:
            raise error
        return written

    monkeypatch.setattr(emit_vex, "is_available", lambda: available)
    monkeypatch.setattr(emit_vex, "emit", fake_emit)
    return calls


def stub_export(monkeypatch: pytest.MonkeyPatch, written: tuple[Path, ...] = (),
                reason: str = "") -> list[Path]:
    """Replace the export stage, recording each call and answering (written, reason)."""
    calls: list[Path] = []

    def fake_export(app_artifacts: Path) -> tuple[list[Path], str]:
        """Record the artifact directory and answer the export contract."""
        calls.append(app_artifacts)
        return list(written), reason

    monkeypatch.setattr(export_reports, "export_all", fake_export)
    return calls


def stub_ai_report(monkeypatch: pytest.MonkeyPatch, written: Path | None = None,
                   error: Exception | None = None) -> list[Path]:
    """Replace the optional AI-formatted view, recording what it was asked to format.

    Answers the page path the real stage would return, so no repaired test
    prints `wrote None`; `error` is how a test asks for the degrade path.
    """
    calls: list[Path] = []

    def fake_format(app_artifacts: Path) -> Path:
        """Record the artifact directory, then answer with a page or refuse."""
        calls.append(app_artifacts)
        if error is not None:
            raise error
        return written if written is not None else app_artifacts / ai_report.AI_REPORT_NAME

    monkeypatch.setattr(ai_report, "format_report", fake_format)
    return calls
