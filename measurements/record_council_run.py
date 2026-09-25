"""Run one council audit and keep what it wrote, beside what produced it.

A council run's output moves with what its command line does not show: the commit,
edits in `src/`, and where Ollama placed the models, which can shift output even at
temperature 0. So this runs the command after `--` into `council_runs/`:

    NAME.report.txt      the text report the run wrote, byte for byte
    NAME.report.json     the audit record the run wrote, byte for byte
    NAME.report.html     the page the run wrote, byte for byte
    NAME.progress.txt    stderr: a line per model call, then the audit's line
                         naming the reports it wrote, in a directory since gone
    NAME.provenance.txt  the command, the commit, `git status --short src/` and
                         `ollama ps` at launch, the start, the end, the exit code,
                         and `ollama ps` at the end

What the provenance holds, and how it is asked for, is `run_provenance`; where
the audit runs, so that the project's own `reports/` is never written, is
`run_directory`. The launch half is written first, so a run killed half way
still says what it was, and a used name is refused rather than a run replaced.

**Stdout is not kept.** When the audit ran it is one of the three renderings --
the text, for the default format, byte for byte -- and when it could not run it
is nothing, the reason going to stderr, which the progress file keeps. One edge
loses a rendering: an audit whose scan ran and whose report write then failed
exits 2, and its stdout, which held the only full rendering, is not kept.

    python measurements/record_council_run.py full -- audit fetched/vulnscout \\
        --council-member qwen2.5:7b-instruct --council-member llama3.2:latest
"""

import shutil
import subprocess
import sys
import tempfile
from dataclasses import astuple, dataclass
from pathlib import Path

import run_provenance
from run_directory import keep_reports, link_project
from run_provenance import REPOSITORY_ROOT, RecordingFailed, loopback_environment

RUNS = REPOSITORY_ROOT / "measurements" / "council_runs"

SEPARATOR = "--"
USAGE = "usage: record_council_run.py NAME -- COMMAND [ARGUMENT ...]"
REPORT_SUFFIX = ".report.txt"
RECORD_SUFFIX = ".report.json"
PAGE_SUFFIX = ".report.html"
PROGRESS_SUFFIX = ".progress.txt"
PROVENANCE_SUFFIX = ".provenance.txt"
WORKING_PREFIX = "council-run-"
COULD_NOT_RECORD = 2


@dataclass(frozen=True)
class Invocation:
    """What to call the run, and the command it runs."""

    name: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class RunFiles:
    """The five files one run writes."""

    report: Path
    record: Path
    page: Path
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
    """Name the five files a run called `name` writes into `directory`."""
    return RunFiles(
        report=directory / f"{name}{REPORT_SUFFIX}",
        record=directory / f"{name}{RECORD_SUFFIX}",
        page=directory / f"{name}{PAGE_SUFFIX}",
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
    taken = [str(one) for one in astuple(files) if one.exists()]
    if taken:
        raise RecordingFailed(f"a run is already recorded there: {', '.join(taken)}")


def run_apart(command: tuple[str, ...], files: RunFiles, root: Path) -> int:
    """Run the audit away from the project's `reports/`, end the provenance, keep the reports."""
    with tempfile.TemporaryDirectory(prefix=WORKING_PREFIX) as made:
        working = Path(made)
        link_project(root, working)
        exit_code = run_command(command, files.progress, working)
        with files.provenance.open("a", encoding="utf-8") as provenance:
            provenance.write(run_provenance.end_of(exit_code))
        keep_reports(
            working, text=files.report, record=files.record, page=files.page, exit_code=exit_code,
        )
    return exit_code


def run_command(command: tuple[str, ...], progress_file: Path, working: Path) -> int:
    """Run the audit with its error stream written straight to the progress file."""
    # Opened as bytes: the audit writes to it itself, and nothing here re-encodes it.
    with progress_file.open("wb") as progress:
        finished = subprocess.run(
            command, stdout=subprocess.DEVNULL, stderr=progress, cwd=working,
            env=loopback_environment(),
        )
    return finished.returncode


def refused(fault: Exception) -> int:
    """Say why this run was not recorded, or not recorded whole, and give the code for it."""
    print(f"record_council_run: {fault}", file=sys.stderr)
    return COULD_NOT_RECORD


def main(argv: list[str], directory: Path = RUNS, root: Path = REPOSITORY_ROOT) -> int:
    """Record one run: its launch before it starts, its end once it stops, then its reports."""
    try:
        invocation = parse_invocation(argv)
        refuse_unrunnable(invocation.command, directory)
        files = run_files(invocation.name, directory)
        refuse_overwrite(files)
        launched = run_provenance.launch_of(invocation.command)
    except RecordingFailed as fault:
        return refused(fault)
    files.provenance.write_text(launched, encoding="utf-8")
    try:
        return run_apart(invocation.command, files, root)
    except (RecordingFailed, OSError) as fault:
        return refused(fault)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
