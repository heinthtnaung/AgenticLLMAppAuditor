"""What a recorded council run was launched from, and how it ended.

A council run's output moves with what its command line does not show: the
commit, edits in `src/`, and where Ollama placed the models, which can shift
output even at temperature 0. So git and `ollama ps` are asked at launch, and
`ollama ps` and the clock again at the end, and both are written down as text.

`ollama ps` shows what is loaded at that instant, so a member loaded and evicted
between the two is in neither. The times are this script's: `src/` reads no clock.
"""

import os
import shlex
import subprocess
from datetime import datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

GIT_COMMIT = ("git", "rev-parse", "HEAD")
GIT_SOURCE_STATUS = ("git", "status", "--short", "src/")
OLLAMA_PS = ("ollama", "ps")
CAPTURE_TIMEOUT_SECONDS = 30
# The audit reaches Ollama on loopback, which the corporate proxy answers 502.
LOOPBACK = "localhost,127.0.0.1"
INDENT = "  "


class RecordingFailed(Exception):
    """Something this script needs before it may start a run is missing."""


def launch_of(command: tuple[str, ...]) -> str:
    """Ask what a run is launched from, and write it down before it runs."""
    return launch_section(
        command, captured(GIT_COMMIT), captured(GIT_SOURCE_STATUS), captured(OLLAMA_PS), now(),
    )


def end_of(exit_code: int) -> str:
    """Write how a run ended, asking Ollama and the clock once it is over."""
    return end_section(now(), exit_code, ollama_at_end())


def indented(output: str) -> list[str]:
    """Put each line a tool printed under its heading."""
    return [f"{INDENT}{line}" for line in output.splitlines()]


def launch_section(command: tuple[str, ...], commit: str, source: str, ollama: str,
                   started: str) -> str:
    """Write what a run was launched from, before it runs."""
    return "\n".join([
        f"command: {shlex.join(command)}",
        f"commit:  {commit.strip()}",
        "src/ changes at launch:", *indented(source),
        "ollama ps at launch:", *indented(ollama),
        f"started: {started}",
    ]) + "\n"


def end_section(ended: str, exit_code: int, ollama: str) -> str:
    """Write how a run ended, and what Ollama had loaded by then."""
    return "\n".join([
        f"ended:   {ended}", f"exit:    {exit_code}", "ollama ps at end:", *indented(ollama),
    ]) + "\n"


def loopback_environment() -> dict[str, str]:
    """Give this environment with loopback kept off the proxy."""
    return {**os.environ, "NO_PROXY": LOOPBACK, "no_proxy": LOOPBACK}


def captured(command: tuple[str, ...]) -> str:
    """Run one short command and give what it printed, refusing to guess if it failed."""
    try:
        finished = subprocess.run(
            command, capture_output=True, text=True, cwd=REPOSITORY_ROOT,
            env=loopback_environment(), timeout=CAPTURE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as fault:
        raise RecordingFailed(f"{shlex.join(command)} could not run: {fault}") from fault
    if finished.returncode != 0:
        said = finished.stderr.strip()
        raise RecordingFailed(f"{shlex.join(command)} exited {finished.returncode}: {said}")
    return finished.stdout


def ollama_at_end() -> str:
    """Give `ollama ps` once the run is over, or why it could not be read."""
    # The exit code is already in hand, so a failure here is recorded, not raised.
    try:
        return captured(OLLAMA_PS)
    except RecordingFailed as fault:
        return f"unavailable: {fault}"


def now() -> str:
    """Give the wall-clock time with its offset, to the second."""
    return datetime.now().astimezone().isoformat(timespec="seconds")
