"""Syft: the components a directory declares, handed on in this project's terms.

A thin wrapper. It runs the tool and hands the JSON to `deps.syft_report`, which
knows Syft's own field names; this file knows only how to reach the tool. The two
change for different reasons -- a flag or a version string here, a field Syft
renamed there.

Syft missing is a normal answer and not a crash: `is_available` lets a caller
report an audit with no components, and say why, rather than fail the run.

"""

import shutil
from pathlib import Path

from deps.scanner import (
    as_directory,
    refuse_missing_directory,
    run_json_scanner,
    run_scanner,
)
from deps.syft_report import Catalogue, read_catalogue

SYFT_EXECUTABLE = "syft"
SCAN_SUBCOMMAND = "scan"
DIRECTORY_SCHEME = "dir:"
JSON_FORMAT = ("-o", "syft-json")
VERSION_FLAG = "--version"


def is_available() -> bool:
    """Say whether Syft is installed, so a caller can report no components rather than fail."""
    return shutil.which(SYFT_EXECUTABLE) is not None


def installed_version() -> str:
    """Give the Syft version on this machine, as Syft itself reports it."""
    # Asked rather than configured: a provenance field a person types is a claim
    # nobody checked, and the whole point of it is that the run is checkable.
    said = run_scanner([SYFT_EXECUTABLE, VERSION_FLAG]).strip()
    return said.removeprefix(f"{SYFT_EXECUTABLE} ").strip() or said


def scan_directory(directory: str | Path) -> Catalogue:
    """Run Syft over a directory and give what it catalogued, joinable or not."""
    scanned = as_directory(directory)
    refuse_missing_directory(scanned)
    return read_catalogue(run_json_scanner(build_command(scanned)))


def build_command(directory: Path) -> list[str]:
    """Build the Syft command line for one directory."""
    return [
        SYFT_EXECUTABLE,
        SCAN_SUBCOMMAND,
        f"{DIRECTORY_SCHEME}{directory}",
        *JSON_FORMAT,
    ]
