"""Running the auditor's CLI from a test, and stubbing the generator it calls.

Several test files drive the CLI or its dependency rules. The argv shim, the
`<artifacts-dir>/<app>/<name>` layout, the Syft stub and the subprocess ban are
spelled once here, so a change to any of them is a change in one place.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from deps import syft_runner
from main import main

# What the stubbed generator reports its own version as. Any string would do;
# this is the one the recorded corpus scans were taken from.
STUB_GENERATOR_VERSION = "1.51.0"

# A scan that found nothing, for the tests that never get as far as scanning.
EMPTY_SCAN = {"components": []}


def run_cli(monkeypatch: pytest.MonkeyPatch, repo_path: Path, artifacts_dir: Path) -> int:
    """Run the CLI once with the given repo and artifacts directory."""
    argv = ["main.py", str(repo_path), "--artifacts-dir", str(artifacts_dir)]
    monkeypatch.setattr(sys, "argv", argv)
    return main()


def stub_syft(monkeypatch: pytest.MonkeyPatch, scan_result: dict) -> None:
    """Replace every Syft call, so no subprocess runs and no tool is required.

    All three are patched, `is_available` included. An earlier copy of this
    stub left that one real, which quietly made six offline tests depend on
    whether the machine running them happened to have Syft installed.
    """
    monkeypatch.setattr(syft_runner, "is_available", lambda: True)
    monkeypatch.setattr(syft_runner, "scan", lambda app_dir: scan_result)
    monkeypatch.setattr(syft_runner, "generator_version", lambda: STUB_GENERATOR_VERSION)


def read_artifact(artifacts_dir: Path, app: str, name: str) -> dict:
    """Read one artifact a run left under <artifacts-dir>/<app>/."""
    return json.loads((artifacts_dir / app / name).read_text(encoding="utf-8"))


def forbid_subprocesses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any attempt to start a process fail the test."""
    def boom(*args, **kwargs) -> None:
        """Fail the test rather than let a real process start."""
        raise AssertionError(f"the auditor started a subprocess: {args}")

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
