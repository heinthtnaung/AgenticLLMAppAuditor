"""Trivy: the advisories published against a directory's components, indexed by purl.

A thin wrapper, offline by construction. It runs the tool and hands the JSON to
`deps.trivy_report`, which knows Trivy's own field names; this file knows only
how to reach the tool. The two change for different reasons -- a flag, a
subcommand or a version string here, a field Trivy renamed there.

A scan must never reach the network, so every flag that guarantees it lives in
one tuple and no call site can assemble a command without them. The other half
of an offline scan -- that the pinned database is there at all -- is
`deps.trivy_database`, and it is asked before the scan, not after.
"""

import shutil
from pathlib import Path

from deps.scanner import (
    ScannerFailed,
    as_directory,
    refuse_missing_directory,
    run_json_scanner,
    run_scanner,
)
from deps.trivy_report import Advisory, read_advisories

TRIVY_EXECUTABLE = "trivy"
FILESYSTEM_SUBCOMMAND = "fs"
JSON_FORMAT = ("--format", "json")
VULNERABILITIES_ONLY = ("--scanners", "vuln")
VERSION_FLAG = "--version"

# Trivy prints its own version unindented and the database's schema version
# indented under a heading, so the margin is what tells the two apart.
VERSION_PREFIX = "Version:"

# The whole offline guarantee, in one place so a command cannot be built without
# it. Trivy exits non-zero on a flag it no longer knows, so a flag dropped in a
# later release fails the run loudly instead of quietly letting a scan phone out.
REQUIRED_OFFLINE_FLAGS: tuple[str, ...] = (
    "--skip-db-update",
    "--offline-scan",
    "--disable-telemetry",
    "--skip-version-check",
)


def is_available() -> bool:
    """Say whether Trivy is installed, so a caller can report no advisories rather than fail."""
    return shutil.which(TRIVY_EXECUTABLE) is not None


def installed_version() -> str:
    """Give the Trivy version on this machine, as Trivy itself reports it."""
    said = run_scanner([TRIVY_EXECUTABLE, VERSION_FLAG])
    for line in said.splitlines():
        if line.startswith(VERSION_PREFIX):
            return line.removeprefix(VERSION_PREFIX).strip()
    raise ScannerFailed(f"{TRIVY_EXECUTABLE} did not say which version it is: {said.strip()!r}")


def scan_directory(directory: str | Path) -> dict[str, tuple[Advisory, ...]]:
    """Run Trivy over a directory and give its advisories, indexed by versioned purl."""
    scanned = as_directory(directory)
    refuse_missing_directory(scanned)
    return read_advisories(run_json_scanner(build_command(scanned)))


def build_command(directory: Path) -> list[str]:
    """Build the Trivy command line for one directory, offline by construction."""
    return [
        TRIVY_EXECUTABLE,
        FILESYSTEM_SUBCOMMAND,
        *JSON_FORMAT,
        *VULNERABILITIES_ONLY,
        *REQUIRED_OFFLINE_FLAGS,
        str(directory),
    ]
