"""Guards on running Syft: the command, the version it reports, and what it refuses."""

import pytest

from deps import syft_runner
from deps.scanner import ScannerUnavailable
from deps.syft_runner import build_command, installed_version, is_available, scan_directory
from samples import NOT_PATHS, syft_artifact, syft_report_of

def test_the_command_scans_the_directory_as_a_directory(tmp_path):
    command = build_command(tmp_path)
    assert command[0] == "syft"
    assert f"dir:{tmp_path}" in command
    assert command[-2:] == ["-o", "syft-json"]


def test_availability_is_read_from_the_path(monkeypatch):
    monkeypatch.setattr(syft_runner.shutil, "which", lambda name: None)
    assert is_available() is False
    monkeypatch.setattr(syft_runner.shutil, "which", lambda name: "/usr/bin/syft")
    assert is_available() is True


def test_an_absent_syft_is_reported_rather_than_crashing_out_of_nowhere(monkeypatch, tmp_path):
    monkeypatch.setattr(syft_runner.shutil, "which", lambda name: None)
    with pytest.raises(ScannerUnavailable, match="not installed"):
        scan_directory(tmp_path)


def test_a_directory_that_is_not_there_is_refused_before_syft_is_reached(tmp_path):
    with pytest.raises(ValueError, match="is not a directory to scan"):
        scan_directory(tmp_path / "absent")


def test_a_directory_given_as_a_string_scans_what_the_path_scans(monkeypatch, tmp_path):
    # A directory named on a command line reaches here as a string. It must scan,
    # and Syft must be handed the command the Path would have built.
    commands = []

    def record(command):
        """Stand in for Syft, keeping the command line and answering with one artifact."""
        commands.append(command)
        return syft_report_of(syft_artifact())

    monkeypatch.setattr(syft_runner, "run_json_scanner", record)
    scanned = scan_directory(f"{tmp_path}/")
    assert [component.name for component in scanned.components] == ["django"]
    assert scanned == scan_directory(tmp_path)
    assert commands[0] == commands[1]


@pytest.mark.parametrize("value, named", NOT_PATHS)
def test_a_directory_that_is_no_kind_of_path_is_refused_by_its_type(value, named):
    with pytest.raises(TypeError, match=f"must be a str or a Path, not {named}"):
        scan_directory(value)


@pytest.mark.parametrize(
    ("said", "expected"),
    [("syft 1.52.0\n", "1.52.0"), ("1.52.0", "1.52.0"), ("syft 1.52.0 (dev)", "1.52.0 (dev)")],
    ids=["as syft prints it", "bare", "with a suffix"],
)
def test_the_version_is_asked_of_syft_and_stripped_of_its_own_name(monkeypatch, said, expected):
    # The field exists to make a run checkable. Leaving the prefix on puts
    # "syft 1.52.0" where "1.52.0" belongs, and nothing downstream would notice.
    monkeypatch.setattr(syft_runner, "run_scanner", lambda command: said)
    assert installed_version() == expected


def test_the_version_command_asks_syft_and_nothing_else(monkeypatch):
    asked = []

    def remember(command):
        asked.append(command)
        return "syft 1.52.0"

    monkeypatch.setattr(syft_runner, "run_scanner", remember)
    installed_version()
    assert asked == [["syft", "--version"]]
