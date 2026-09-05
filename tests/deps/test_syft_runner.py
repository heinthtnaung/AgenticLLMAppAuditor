"""The one part of the SBOM path that touches the outside world.

Syft is an external prerequisite, so everything here either works without it or
skips loudly. The settings that stop it phoning home are asserted, because the
offline guarantee cannot be checked from inside the auditor's own process.
"""

from pathlib import Path

import pytest
from deps import syft_runner
from dependency_fixtures import PYPI_DECLARED

LIBRARY = "library"

# A manifest Syft really reads, so the one test that runs the tool has
# something to find. Written by the test: the pinned app it used to scan is
# gone, so the recorded generator output can no longer be re-verified against a
# real repository -- only the tool's own reading of a manifest can be.
MANIFEST_NAME = "requirements.txt"
PINNED = {name: constraint for name, constraint in PYPI_DECLARED.items()
          if constraint.startswith("==")}


def test_update_check_is_disabled() -> None:
    """Syft checks for its own updates unless told not to; the auditor is offline."""
    assert syft_runner.SYFT_ENV["SYFT_CHECK_FOR_APP_UPDATE"] == "false"


def test_remote_licence_lookup_is_disabled() -> None:
    """Licence lookup would fetch from the network, so it stays off."""
    assert syft_runner.SYFT_ENV["SYFT_PYTHON_SEARCH_REMOTE_LICENSES"] == "false"


def test_version_guessing_setting_matches_the_flag_recorded_in_the_sbom() -> None:
    """The environment and GUESS_UNPINNED agree, or the artifact would misreport it."""
    expected = "true" if syft_runner.GUESS_UNPINNED else "false"
    assert syft_runner.SYFT_ENV["SYFT_PYTHON_GUESS_UNPINNED_REQUIREMENTS"] == expected


def test_is_available_answers_yes_or_no() -> None:
    """Availability is a plain bool, so a caller can skip rather than crash."""
    assert isinstance(syft_runner.is_available(), bool)


def test_scanning_a_missing_directory_fails_clearly(tmp_path: Path) -> None:
    """A bad path is rejected by name, before any subprocess is started."""
    missing = tmp_path / "no-such-app"
    with pytest.raises(NotADirectoryError) as error:
        syft_runner.scan(missing)
    assert str(missing) in str(error.value)


def test_scanning_a_file_is_rejected(tmp_path: Path) -> None:
    """A file is not an app directory."""
    target = tmp_path / "requirements.txt"
    target.write_text("streamlit\n", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        syft_runner.scan(target)


def test_missing_syft_points_at_the_prerequisites(tmp_path: Path, monkeypatch) -> None:
    """Without the tool installed the error names it and where to read about it."""
    monkeypatch.setattr(syft_runner.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError) as error:
        syft_runner.scan(tmp_path)
    assert "syft" in str(error.value)
    assert "README" in str(error.value)


def write_pinned_manifest(root: Path) -> Path:
    """Write a requirements.txt pinning each exactly-versioned recorded package."""
    lines = [f"{name}{constraint}" for name, constraint in PINNED.items()]
    (root / MANIFEST_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def test_syft_scan_reports_the_packages_the_manifest_pins(tmp_path: Path) -> None:
    """The real tool, when installed: what it reports for a manifest written here.

    The only test in the suite that runs Syft. It skips rather than fails when
    the prerequisite is absent, so the rest of Phase 2 stays runnable anywhere.
    The manifest is written by the test, so this checks the tool still reads a
    pinned requirement the way the recorded fixtures assume -- it can no longer
    re-verify those fixtures against a real repository.
    """
    if not syft_runner.is_available():
        pytest.skip("syft is not installed - see the README prerequisites")
    output = syft_runner.scan(write_pinned_manifest(tmp_path))
    assert isinstance(output, dict)
    assert isinstance(output.get("components"), list)
    libraries = {
        (c["name"], c.get("version"))
        for c in output["components"] if c.get("type") == LIBRARY
    }
    expected = {(name, constraint.removeprefix("==")) for name, constraint in PINNED.items()}
    assert expected and libraries >= expected
