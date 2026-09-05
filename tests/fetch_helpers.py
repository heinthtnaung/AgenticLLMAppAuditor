"""Shared setup for the fetcher's tests: a git that never reaches the network.

No test in this suite may clone anything, so every one of them replaces the one
place `fetch_repo` starts a process. Two stand-ins are needed, at two different
depths: `FakeGit` replaces `fetch_repo._run` and pretends a clone succeeded,
while the two installers below replace `subprocess.run` itself, so the real
`_run` -- and its translation of a timeout or a non-zero exit into a clear
error -- is the code under test.
"""

import shutil
import subprocess
from pathlib import Path

import fetch_repo
from fetch_repo import HISTORY_DIR

URL = "https://github.com/owner/demo.git"
NAME = "demo"
COMMIT = "0123456789abcdef0123456789abcdef01234567"
COMMIT_DATE = "2025-06-25T14:58:42+01:00"

SOURCE_FILE = "agent.py"
SOURCE_TEXT = "print('hello')\n"
PARTIAL_FILE = "half-written.pack"
PARTIAL_TEXT = "an object that never finished arriving"

CLONE_FAILED = "fatal: repository not found"

# `shutil.which` must find something for `_run` to get as far as the stand-in,
# and the tests must not depend on the machine having git installed.
FAKE_GIT_PATH = "/usr/bin/git"


def download_root(tmp_path: Path) -> Path:
    """The directory a test fetches into: always under tmp_path, never the real one."""
    return tmp_path / "fetched"


class FakeGit:
    """Stands in for `fetch_repo._run`: writes the tree a clone would, answers the pin."""

    def __init__(self, commit: str = COMMIT, commit_date: str = COMMIT_DATE) -> None:
        self.commit = commit
        self.commit_date = commit_date
        self.calls: list[list[str]] = []
        self.history_present_at_pin: list[bool] = []

    def __call__(self, arguments: list[str], cwd: Path | None = None) -> str:
        """Answer one git command from memory, recording what was asked."""
        self.calls.append(list(arguments))
        if arguments[0] == "clone":
            plant_clone(Path(arguments[-1]))
            return ""
        if arguments[0] == "rev-parse":
            self.history_present_at_pin.append((Path(cwd) / HISTORY_DIR).is_dir())
            return f"{self.commit}\n"
        if arguments[0] == "log":
            return f"{self.commit_date}\n"
        raise AssertionError(f"the fetcher ran an unexpected git command: {arguments}")


def install_fake_git(monkeypatch) -> FakeGit:
    """Replace the fetcher's one process launch with a stand-in, and return it."""
    fake = FakeGit()
    monkeypatch.setattr(fetch_repo, "_run", fake)
    return fake


def plant_clone(destination: Path) -> None:
    """Write the tree a successful clone leaves behind, history directory and all."""
    (destination / HISTORY_DIR).mkdir(parents=True)
    (destination / HISTORY_DIR / "config").write_text("[core]\n", encoding="utf-8")
    (destination / SOURCE_FILE).write_text(SOURCE_TEXT, encoding="utf-8")


def plant_partial_clone(argv: list[str]) -> Path:
    """Write the half-finished tree a clone leaves on disk before it fails."""
    destination = Path(argv[-1])
    (destination / HISTORY_DIR).mkdir(parents=True)
    (destination / PARTIAL_FILE).write_text(PARTIAL_TEXT, encoding="utf-8")
    return destination


def install_recording_git(monkeypatch) -> list[list[str]]:
    """Record the argv the fetcher composes, at subprocess depth, and run nothing."""
    seen: list[list[str]] = []

    def run(argv, **kwargs):
        seen.append(list(argv))
        if "clone" in argv:
            plant_clone(Path(argv[-1]))
            return subprocess.CompletedProcess(argv, 0, "", "")
        answer = COMMIT if "rev-parse" in argv else COMMIT_DATE
        return subprocess.CompletedProcess(argv, 0, f"{answer}\n", "")

    monkeypatch.setattr(shutil, "which", lambda program: FAKE_GIT_PATH)
    monkeypatch.setattr(subprocess, "run", run)
    return seen


def install_failing_git(monkeypatch, error: str = CLONE_FAILED) -> None:
    """Make a clone write a partial tree and then exit non-zero, as a failed fetch does."""
    def run(argv, **kwargs):
        plant_partial_clone(argv)
        return subprocess.CompletedProcess(argv, 1, "", error)

    monkeypatch.setattr(shutil, "which", lambda program: FAKE_GIT_PATH)
    monkeypatch.setattr(subprocess, "run", run)


def install_hanging_git(monkeypatch) -> None:
    """Make a clone write a partial tree and then time out, as a stalled fetch does."""
    def run(argv, **kwargs):
        plant_partial_clone(argv)
        raise subprocess.TimeoutExpired(argv, fetch_repo.TIMEOUT_SECONDS)

    monkeypatch.setattr(shutil, "which", lambda program: FAKE_GIT_PATH)
    monkeypatch.setattr(subprocess, "run", run)
