"""Guards on running an external scanner: absent, failing, and not answering in JSON."""

import subprocess
import sys
from pathlib import Path

import pytest

from deps.scanner import (
    ScannerFailed,
    ScannerUnavailable,
    as_directory,
    is_installed,
    read_json,
    refuse_missing_directory,
    refuse_unavailable,
    run_json_scanner,
)
from samples import NOT_PATHS

# Not a scanner: a scanner is never run in a test, so the subprocess paths are
# exercised with the interpreter already running them.
INTERPRETER = sys.executable


def python_command(source: str) -> list[str]:
    """Build a command that runs one line of Python, standing in for a scanner."""
    return [INTERPRETER, "-c", source]


def test_an_installed_executable_is_found():
    assert is_installed(INTERPRETER) is True


def test_an_absent_executable_is_not_found():
    assert is_installed("no-such-scanner-on-this-machine") is False


def test_an_absent_scanner_is_refused_by_name():
    with pytest.raises(ScannerUnavailable, match="no-such-scanner"):
        refuse_unavailable("no-such-scanner")


def test_an_absent_scanner_is_refused_before_anything_is_spawned():
    with pytest.raises(ScannerUnavailable, match="is not installed"):
        run_json_scanner(["no-such-scanner", "--format", "json"])


def test_a_path_that_is_not_a_directory_is_refused(tmp_path):
    with pytest.raises(ValueError, match="is not a directory to scan"):
        refuse_missing_directory(tmp_path / "absent")


def test_a_file_is_not_a_directory_to_scan(tmp_path):
    manifest = tmp_path / "requirements.txt"
    manifest.write_text("Django==2.2.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="is not a directory to scan"):
        refuse_missing_directory(manifest)


def test_a_directory_is_accepted(tmp_path):
    assert refuse_missing_directory(tmp_path) is None


def test_a_directory_given_as_a_string_is_accepted(tmp_path):
    assert refuse_missing_directory(str(tmp_path)) is None


def test_a_directory_given_as_a_string_names_the_same_directory(tmp_path):
    # A path that came off a command line arrives as a string, often with a
    # trailing separator. It has to name the directory the Path names.
    assert as_directory(f"{tmp_path}/") == as_directory(tmp_path) == tmp_path


def test_a_missing_directory_given_as_a_string_is_refused_the_same_way(tmp_path):
    with pytest.raises(ValueError, match="is not a directory to scan"):
        refuse_missing_directory(str(tmp_path / "absent"))


@pytest.mark.parametrize("value, named", NOT_PATHS)
def test_a_directory_that_is_no_kind_of_path_is_refused_by_its_type(value, named):
    # Not an AttributeError two frames down in a scanner: the entry point says
    # what it was handed.
    with pytest.raises(TypeError, match=f"must be a str or a Path, not {named}"):
        refuse_missing_directory(value)


def test_a_json_report_comes_back_parsed():
    report = run_json_scanner(python_command('print(\'{"Results": []}\')'))
    assert report == {"Results": []}


def test_a_non_zero_exit_is_refused_and_quotes_what_the_tool_said():
    # A flag a later release drops arrives here: Trivy exits non-zero on a flag it
    # does not know, and that must fail the run rather than pass unnoticed.
    command = python_command(
        "import sys; sys.stderr.write('FATAL unknown flag: --skip-db-update'); sys.exit(1)"
    )
    with pytest.raises(ScannerFailed, match="unknown flag: --skip-db-update"):
        run_json_scanner(command)


def test_a_failure_that_said_nothing_is_still_refused():
    with pytest.raises(ScannerFailed, match="exited 3"):
        run_json_scanner(python_command("raise SystemExit(3)"))


def test_output_that_is_not_json_is_refused():
    with pytest.raises(ScannerFailed, match="did not return readable JSON"):
        run_json_scanner(python_command("print('not a report')"))


def test_empty_output_is_refused_rather_than_read_as_nothing_found():
    with pytest.raises(ScannerFailed, match="did not return readable JSON"):
        read_json("trivy", "")


def test_the_scanner_is_run_without_a_shell(monkeypatch):
    # An argument list, never a string: a repository path with a space in it must
    # not become two arguments, and must not be able to become a second command.
    seen: dict = {}

    def record(command, **options):
        """Stand in for subprocess.run and keep what it was handed."""
        seen["command"] = command
        seen["options"] = options
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    monkeypatch.setattr(subprocess, "run", record)
    run_json_scanner([INTERPRETER, "fs", str(Path("/tmp/a repo"))])
    assert seen["command"][-1] == "/tmp/a repo"
    assert "shell" not in seen["options"]
