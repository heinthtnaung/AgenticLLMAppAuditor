"""Which ecosystem a repository declares, and the repository the CLI refuses to read.

Nothing tested `dependencies_readable` before, so the rule it enforces arrived
unguarded. One SBOM holds one ecosystem: a repository declaring both a Python
and an npm manifest is refused rather than half-read, because reporting only
the Python half would understate the tree while looking complete.

Split from test_main_npm_dependencies.py, which runs the CLI end to end. This
file never writes an artifact -- it only asks what the repository declares.
"""

from pathlib import Path

import pytest

from cli_helpers import EMPTY_SCAN, stub_syft
from dependency_fixtures import NPM_MANIFEST, PYPI_MANIFEST, TINY_PACKAGE_JSON
from deps import syft_runner
from deps.package_names import NPM, PYPI
from main import declared_ecosystems, dependencies_readable

REQUIREMENTS = "streamlit\n"


def available_syft(monkeypatch: pytest.MonkeyPatch) -> None:
    """Report the generator as installed, so the manifest rules are what is under test.

    Nothing here ever reaches a scan, so the stubbed generator finds nothing --
    but it is the shared stub, which patches all three calls rather than one.
    """
    stub_syft(monkeypatch, EMPTY_SCAN)


def write_python_manifest(app_dir: Path) -> None:
    """Give the repository a requirements.txt."""
    (app_dir / PYPI_MANIFEST).write_text(REQUIREMENTS, encoding="utf-8")


def write_npm_manifest(app_dir: Path) -> None:
    """Give the repository a package.json."""
    (app_dir / NPM_MANIFEST).write_text(TINY_PACKAGE_JSON, encoding="utf-8")


def test_a_python_repo_declares_the_pypi_ecosystem(tmp_path: Path) -> None:
    """A requirements.txt says the app's dependencies resolve on PyPI."""
    write_python_manifest(tmp_path)
    assert declared_ecosystems(tmp_path) == [PYPI]


def test_an_npm_repo_declares_the_npm_ecosystem(tmp_path: Path) -> None:
    """A package.json says they resolve on npm instead."""
    write_npm_manifest(tmp_path)
    assert declared_ecosystems(tmp_path) == [NPM]


def test_a_repo_declaring_nothing_declares_no_ecosystem(tmp_path: Path) -> None:
    """No manifest is an answer, not a default: guessing PyPI would invent a tree."""
    assert declared_ecosystems(tmp_path) == []


def test_a_repo_declaring_both_reports_both(tmp_path: Path) -> None:
    """Both are reported, so the caller can refuse rather than silently pick one."""
    write_python_manifest(tmp_path)
    write_npm_manifest(tmp_path)
    assert declared_ecosystems(tmp_path) == [PYPI, NPM]


def test_an_npm_only_repo_can_be_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The change that mattered: a JS app is no longer refused for having no requirements.txt."""
    available_syft(monkeypatch)
    write_npm_manifest(tmp_path)
    assert dependencies_readable(tmp_path) == (True, "")


def test_a_python_only_repo_can_still_be_read(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The Python path did not move when npm arrived."""
    available_syft(monkeypatch)
    write_python_manifest(tmp_path)
    assert dependencies_readable(tmp_path) == (True, "")


def test_a_repo_with_no_manifest_is_refused(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing to read is reported as a reason, not as a failure."""
    available_syft(monkeypatch)
    readable, reason = dependencies_readable(tmp_path)
    assert readable is False
    assert reason == "no dependency manifest found"


def test_a_repo_declaring_both_ecosystems_is_refused(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Half a tree looks like a whole one, so the mixed repo gets no bill at all."""
    available_syft(monkeypatch)
    write_python_manifest(tmp_path)
    write_npm_manifest(tmp_path)
    assert dependencies_readable(tmp_path)[0] is False


def test_the_mixed_repo_refusal_names_both_manifests(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The message names the two files it found, so the reader can go and look at them."""
    available_syft(monkeypatch)
    write_python_manifest(tmp_path)
    write_npm_manifest(tmp_path)
    reason = dependencies_readable(tmp_path)[1]
    assert "both" in reason
    assert PYPI_MANIFEST in reason and NPM_MANIFEST in reason


def test_a_missing_generator_is_refused_before_the_manifests(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the tool there is no bill to build, whatever the repository declares."""
    monkeypatch.setattr(syft_runner, "is_available", lambda: False)
    write_npm_manifest(tmp_path)
    readable, reason = dependencies_readable(tmp_path)
    assert readable is False
    assert syft_runner.GENERATOR_NAME in reason
