"""Runs Syft over an app directory and returns its CycloneDX output.

The only part of the SBOM path that touches the outside world, so the
normaliser in sbom.py stays pure and testable on a machine without Syft.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

GENERATOR_NAME = "syft"
TIMEOUT_SECONDS = 300

# Syft records only exact `==` pins by default, which on a typical
# requirements.txt means most dependencies vanish. Guessing is enabled and the
# result is labelled, rather than silently dropping what the manifest declares.
GUESS_UNPINNED = True

# Syft checks for its own updates over the network unless told not to. The
# auditor makes no external calls, so this is forced off rather than trusted.
SYFT_ENV = {
    "SYFT_CHECK_FOR_APP_UPDATE": "false",
    "SYFT_PYTHON_GUESS_UNPINNED_REQUIREMENTS": "true" if GUESS_UNPINNED else "false",
    "SYFT_PYTHON_SEARCH_REMOTE_LICENSES": "false",
}


def is_available() -> bool:
    """Say whether Syft is installed, so a caller can skip rather than crash."""
    return shutil.which(GENERATOR_NAME) is not None


def generator_version() -> str:
    """Return the installed Syft version, which is part of the artifact."""
    output = _run(["version", "-o", "json"])
    return json.loads(output).get("version", "unknown")


def scan(app_dir: Path) -> dict:
    """Return Syft's CycloneDX document for an app directory."""
    if not app_dir.is_dir():
        raise NotADirectoryError(f"cannot scan {app_dir}: not a directory")
    return json.loads(_run(["scan", f"dir:{app_dir}", "-o", "cyclonedx-json", "-q"]))


def _run(arguments: list[str]) -> str:
    """Run one Syft command, raising with its own message if it fails."""
    if not is_available():
        raise RuntimeError(
            f"{GENERATOR_NAME} is not installed - see the README prerequisites"
        )
    try:
        done = subprocess.run(
            [GENERATOR_NAME, *arguments], capture_output=True, text=True,
            timeout=TIMEOUT_SECONDS, check=False, env={"PATH": _path(), **SYFT_ENV},
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"{GENERATOR_NAME} timed out after {TIMEOUT_SECONDS}s") from error
    if done.returncode != 0:
        raise RuntimeError(f"{GENERATOR_NAME} {arguments[0]} failed: {done.stderr.strip()}")
    return done.stdout


def _path() -> str:
    """Return a PATH that can find Syft, without inheriting the rest of the environment."""
    return os.environ.get("PATH", "/usr/bin:/bin")
