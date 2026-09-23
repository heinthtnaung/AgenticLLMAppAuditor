"""Guards on running Trivy: the offline flags, the command, and the version it reports."""

import pytest

from deps import trivy_runner
from deps.scanner import ScannerFailed, ScannerUnavailable
from deps.trivy_runner import (
    REQUIRED_OFFLINE_FLAGS,
    build_command,
    installed_version,
    is_available,
    scan_directory,
)
from samples import DJANGO_PURL, NOT_PATHS, trivy_record, trivy_report_of

# Captured from Trivy 0.74.0 over a directory of pinned Python requirements, in
# the order it emitted them, which is not sorted order. Two records were written
# by hand in the same shape: one scored under CVSS v2 only, one with no scores
# and no published fix.
REPORT = "trivy_report.json"
REPORT_WITH_NO_RESULTS = "trivy_report_no_results.json"

EVERY_OFFLINE_FLAG = (
    "--skip-db-update",
    "--offline-scan",
    "--disable-telemetry",
    "--skip-version-check",
)


def test_the_offline_flags_are_all_named_in_one_constant():
    assert set(REQUIRED_OFFLINE_FLAGS) == set(EVERY_OFFLINE_FLAG)


@pytest.mark.parametrize("flag", EVERY_OFFLINE_FLAG)
def test_no_command_can_be_built_without_an_offline_flag(flag, tmp_path):
    assert flag in build_command(tmp_path)


def test_the_command_scans_the_given_directory_for_vulnerabilities(tmp_path):
    command = build_command(tmp_path)
    assert command[:2] == ["trivy", "fs"]
    assert command[-1] == str(tmp_path)
    assert "--scanners" in command and "vuln" in command


def test_availability_is_read_from_the_path(monkeypatch):
    monkeypatch.setattr(trivy_runner.shutil, "which", lambda name: None)
    assert is_available() is False
    monkeypatch.setattr(trivy_runner.shutil, "which", lambda name: "/usr/bin/trivy")
    assert is_available() is True


def test_an_absent_trivy_is_reported_rather_than_crashing_out_of_nowhere(monkeypatch, tmp_path):
    monkeypatch.setattr(trivy_runner.shutil, "which", lambda name: None)
    with pytest.raises(ScannerUnavailable, match="not installed"):
        scan_directory(tmp_path)


def test_a_directory_that_is_not_there_is_refused_before_trivy_is_reached(tmp_path):
    with pytest.raises(ValueError, match="is not a directory to scan"):
        scan_directory(tmp_path / "absent")


def test_a_directory_given_as_a_string_scans_what_the_path_scans(monkeypatch, tmp_path):
    # A directory named on a command line reaches here as a string. It must scan,
    # and Trivy must be handed the command the Path would have built, offline
    # flags and all.
    commands = []

    def record(command):
        """Stand in for Trivy, keeping the command line and answering with one advisory."""
        commands.append(command)
        return trivy_report_of(trivy_record())

    monkeypatch.setattr(trivy_runner, "run_json_scanner", record)
    scanned = scan_directory(f"{tmp_path}/")
    assert list(scanned) == [DJANGO_PURL]
    assert scanned == scan_directory(tmp_path)
    assert commands[0] == commands[1]


@pytest.mark.parametrize("value, named", NOT_PATHS)
def test_a_directory_that_is_no_kind_of_path_is_refused_by_its_type(value, named):
    with pytest.raises(TypeError, match=f"must be a str or a Path, not {named}"):
        scan_directory(value)


def test_the_version_is_asked_of_trivy_rather_than_configured(monkeypatch):
    # The field exists to make a run checkable, and a number somebody types is a
    # claim nobody checked. This tool printed trivy 0.58.1 on a 0.74.0 machine
    # for exactly as long as a person supplied it.
    monkeypatch.setattr(trivy_runner, "run_scanner", lambda command: "Version: 0.74.0\n")
    assert installed_version() == "0.74.0"


def test_the_version_asked_for_is_trivys_own_and_not_the_databases(monkeypatch):
    # Trivy prints its own version unindented and the database's schema version
    # indented under a heading. Taking any line with "Version:" reports 2.
    said = "Version: 0.74.0\nVulnerability DB:\n  Version: 2\n  UpdatedAt: 2026-09-22\n"
    monkeypatch.setattr(trivy_runner, "run_scanner", lambda command: said)
    assert installed_version() == "0.74.0"


def test_the_version_command_asks_trivy_and_nothing_else(monkeypatch):
    asked = []
    def remember(command):
        asked.append(command)
        return "Version: 1"

    monkeypatch.setattr(trivy_runner, "run_scanner", remember)
    installed_version()
    assert asked == [["trivy", "--version"]]


@pytest.mark.parametrize(
    "said",
    ["", "trivy version 0.74.0", "  Version: 2"],
    ids=["nothing", "another shape", "indented"],
)
def test_a_trivy_that_does_not_say_its_version_is_refused(monkeypatch, said):
    monkeypatch.setattr(trivy_runner, "run_scanner", lambda command: said)
    with pytest.raises(ScannerFailed, match="did not say which version it is"):
        installed_version()
