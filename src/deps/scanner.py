"""Running an external scanner: the part Syft and Trivy do identically.

Both are invoked the same way -- a command that writes one JSON report to
stdout -- and both fail in the same three ways: not installed, a non-zero exit,
and output that is not the JSON it promised. Keeping that here is what lets each
runner be little more than its command line and its vocabulary.

A scanner that is not installed raises rather than returning nothing, because
"no components" and "no scanner" are different answers and a caller that cannot
tell them apart will publish the wrong one. `is_installed` is how a caller asks
first.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

# Enough of the tool's own complaint to act on, without pasting a scan log into
# an exception.
STDERR_EXCERPT_LINES = 5

SILENT_FAILURE = "(it said nothing)"


class ScannerUnavailable(RuntimeError):
    """The scanner is not installed here, which is an answer rather than a fault."""


class ScannerFailed(RuntimeError):
    """The scanner ran and gave back something this cannot read."""


def is_installed(executable: str) -> bool:
    """Say whether an executable is on this machine's PATH."""
    return shutil.which(executable) is not None


def run_json_scanner(command: list[str]) -> Any:
    """Run a scanner that writes a JSON report to stdout, and give that report parsed."""
    executable = command[0]
    refuse_unavailable(executable)
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise ScannerFailed(failure_message(executable, completed))
    return read_json(executable, completed.stdout)


def refuse_unavailable(executable: str) -> None:
    """Refuse to scan with a tool this machine does not have."""
    if is_installed(executable):
        return
    raise ScannerUnavailable(
        f"{executable!r} is not installed on this machine; "
        "ask is_available() before scanning and report the gap instead"
    )


def as_path(value: object, described_as: str) -> Path:
    """Give a path argument as a Path, refusing a value that is no kind of path."""
    if isinstance(value, Path):
        return value
    if isinstance(value, str):
        return Path(value)
    raise TypeError(f"{described_as} must be a str or a Path, not {type(value).__name__}")


def as_directory(directory: object) -> Path:
    """Give a directory argument as a Path, so a path off a command line is a path here."""
    return as_path(directory, "A directory to scan")


def refuse_missing_directory(directory: str | Path) -> None:
    """Refuse a path that is not a directory, before anything is spawned."""
    scanned = as_directory(directory)
    if not scanned.is_dir():
        raise ValueError(f"{str(scanned)!r} is not a directory to scan")


def failure_message(executable: str, completed: subprocess.CompletedProcess) -> str:
    """Say that a scanner failed, quoting the end of what it said about it."""
    lines = completed.stderr.strip().splitlines()[-STDERR_EXCERPT_LINES:]
    excerpt = "\n".join(lines) or SILENT_FAILURE
    return f"{executable} exited {completed.returncode}:\n{excerpt}"


def read_json(executable: str, output: str) -> Any:
    """Parse a scanner's report, refusing output that is not the JSON it promised."""
    try:
        return json.loads(output)
    except ValueError as fault:
        raise ScannerFailed(f"{executable} did not return readable JSON: {fault}") from fault
