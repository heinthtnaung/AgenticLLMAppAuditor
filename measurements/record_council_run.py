"""Run one council audit and record what produced it, beside what it printed.

A council run's output moves with what its command line does not show: the
commit, edits in `src/`, and where Ollama placed the models, which shifts output
even at temperature 0. So this runs the command after `--` and records it, the
commit, source state, placement and times beside its output in `council_runs/`:

    NAME.report.txt      stdout, the report
    NAME.progress.txt    stderr, one line per model call
    NAME.provenance.txt  the command, the commit, `git status --short src/` and
                         `ollama ps` at launch, the start, the end, the exit code,
                         and `ollama ps` at the end

The launch half is written before the command starts, so a run killed half way
still says what it was, and a name already used is refused rather than a
recorded run replaced. The times are this script's: `src/` reads no clock.

    python measurements/record_council_run.py full -- audit fetched/vulnscout \\
        --council-member qwen2.5:7b-instruct --council-member llama3.2:latest
"""

import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
RUNS = REPOSITORY_ROOT / "measurements" / "council_runs"

SEPARATOR = "--"
USAGE = "usage: record_council_run.py NAME -- COMMAND [ARGUMENT ...]"
REPORT_SUFFIX = ".report.txt"
PROGRESS_SUFFIX = ".progress.txt"
PROVENANCE_SUFFIX = ".provenance.txt"

GIT_COMMIT = ("git", "rev-parse", "HEAD")
GIT_SOURCE_STATUS = ("git", "status", "--short", "src/")
OLLAMA_PS = ("ollama", "ps")
CAPTURE_TIMEOUT_SECONDS = 30
# The audit reaches Ollama on loopback, which the corporate proxy answers 502.
LOOPBACK = "localhost,127.0.0.1"
INDENT = "  "
COULD_NOT_RECORD = 2


class RecordingFailed(Exception):
    """Something this script needs before it may start a run is missing."""


@dataclass(frozen=True)
class Invocation:
    """What to call the run, and the command it runs."""

    name: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class RunFiles:
    """The three files one run writes."""

    report: Path
    progress: Path
    provenance: Path


def parse_invocation(argv: list[str]) -> Invocation:
    """Read `NAME -- COMMAND...`, refusing anything that would put a file elsewhere."""
    if SEPARATOR not in argv:
        raise RecordingFailed(f"no {SEPARATOR!r} before the command; {USAGE}")
    split = argv.index(SEPARATOR)
    names, command = argv[:split], tuple(argv[split + 1:])
    if len(names) != 1 or not command:
        raise RecordingFailed(f"give exactly one name and a command; {USAGE}")
    if not names[0] or Path(names[0]).name != names[0]:
        raise RecordingFailed(f"{names[0]!r} is no plain file name for a run")
    return Invocation(names[0], command)


def run_files(name: str, directory: Path) -> RunFiles:
    """Name the three files a run called `name` writes into `directory`."""
    return RunFiles(
        report=directory / f"{name}{REPORT_SUFFIX}",
        progress=directory / f"{name}{PROGRESS_SUFFIX}",
        provenance=directory / f"{name}{PROVENANCE_SUFFIX}",
    )


def refuse_unrunnable(command: tuple[str, ...], directory: Path) -> None:
    """Refuse a command or a directory that would fail only after the launch is written."""
    if shutil.which(command[0]) is None:
        raise RecordingFailed(f"{command[0]!r} is not on the path; is the venv active?")
    if not directory.is_dir():
        raise RecordingFailed(f"{directory} is no directory to record a run into")


def refuse_overwrite(files: RunFiles) -> None:
    """Refuse a name already used, because each file there is a run nobody can repeat."""
    taken = [str(one) for one in (files.report, files.progress, files.provenance) if one.exists()]
    if taken:
        raise RecordingFailed(f"a run is already recorded there: {', '.join(taken)}")


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
    """Write how a run ended, and where Ollama had the models by then."""
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


def run_command(command: tuple[str, ...], files: RunFiles) -> int:
    """Run the audit with its two streams written straight to their files."""
    # Opened as bytes: the audit writes to them itself, and nothing here re-encodes it.
    with files.report.open("wb") as report, files.progress.open("wb") as progress:
        finished = subprocess.run(
            command, stdout=report, stderr=progress, cwd=REPOSITORY_ROOT,
            env=loopback_environment(),
        )
    return finished.returncode


def main(argv: list[str], directory: Path = RUNS) -> int:
    """Record one run: its launch before it starts, its end once it stops."""
    try:
        invocation = parse_invocation(argv)
        refuse_unrunnable(invocation.command, directory)
        files = run_files(invocation.name, directory)
        refuse_overwrite(files)
        launched = launch_section(
            invocation.command, captured(GIT_COMMIT), captured(GIT_SOURCE_STATUS),
            captured(OLLAMA_PS), now(),
        )
    except RecordingFailed as fault:
        print(f"record_council_run: {fault}", file=sys.stderr)
        return COULD_NOT_RECORD
    files.provenance.write_text(launched, encoding="utf-8")
    exit_code = run_command(invocation.command, files)
    with files.provenance.open("a", encoding="utf-8") as provenance:
        provenance.write(end_section(now(), exit_code, ollama_at_end()))
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
