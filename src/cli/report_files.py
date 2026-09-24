"""Every rendering of one record, written into `reports/` beside what stdout gets.

**One run, three files.** A council run can take over an hour, and the format
asked for on the command line is only the one printed; the other two are
rendered from the same record and saved too, so nobody repeats that hour to
read the page instead of the text.

**Named after the repository, and never after the time.** `src/` reads no clock,
so a second run of the same repository overwrites its three files. The folder
and the three files are checked before the scan starts, because a place that
cannot take the reports should not cost a whole run to find out about.
"""

import os
from pathlib import Path
from typing import Mapping

from cli.arguments import HTML_FORMAT, JSON_FORMAT, TEXT_FORMAT

# Relative on purpose: the reports land where the operator ran the command.
REPORTS_DIRECTORY = Path("reports")
SUFFIXES = {TEXT_FORMAT: ".txt", JSON_FORMAT: ".json", HTML_FORMAT: ".html"}
ENCODING = "utf-8"
WRITTEN_TO = "reports written to"
# Making a file in a folder needs the right to search it as well as to write it.
CREATE_IN = os.W_OK | os.X_OK


class CannotWriteReports(RuntimeError):
    """The folder or a file the reports go into cannot be written."""


def planned_reports(repository: Path, directory: Path) -> dict[str, Path]:
    """Make the folder and name each format's file, refusing any this run could not write."""
    ready_directory(directory)
    paths = report_paths(repository, directory)
    for path in paths.values():
        refuse_unwritable(path)
    return paths


def ready_directory(directory: Path) -> None:
    """Make the folder the reports go into, refusing one they cannot be written to."""
    if directory.exists() and not directory.is_dir():
        raise CannotWriteReports(f"{directory} exists and is not a folder the reports can go into")
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as fault:
        said = f"cannot make {directory} for the reports: {fault.strerror}"
        raise CannotWriteReports(said) from fault
    if not os.access(directory, CREATE_IN):
        raise CannotWriteReports(f"{directory} is not writable, so no report can go into it")


def refuse_unwritable(path: Path) -> None:
    """Refuse a file the last run left where this run cannot replace it."""
    if path.is_dir():
        raise CannotWriteReports(f"{path} is a folder, so no report can be written there")
    if path.exists() and not os.access(path, os.W_OK):
        raise CannotWriteReports(f"{path} is not writable, so this run cannot replace it")


def repository_name(repository: Path) -> str:
    """Give the name of the directory audited, which is what its reports are called."""
    # Absolute so that `audit .` has a name; `abspath` rather than `resolve`, so
    # a symlinked repository keeps the name it was given rather than its target's.
    name = Path(os.path.abspath(repository)).name
    if not name:
        raise CannotWriteReports(f"{str(repository)!r} has no directory name to name reports by")
    return name


def report_paths(repository: Path, directory: Path) -> dict[str, Path]:
    """Name the file each format of one repository's report is written to."""
    name = repository_name(repository)
    return {one: directory / f"{name}{suffix}" for one, suffix in SUFFIXES.items()}


def write_reports(renderings: Mapping[str, str], paths: Mapping[str, Path]) -> tuple[Path, ...]:
    """Write every rendering to its own file, replacing the last run's, and give the paths."""
    return tuple(written(path, renderings[one]) for one, path in paths.items())


def written(path: Path, text: str) -> Path:
    """Write one rendering, naming the file if it cannot be written."""
    try:
        path.write_text(text, encoding=ENCODING)
    except OSError as fault:
        raise CannotWriteReports(f"cannot write {path}: {fault.strerror}") from fault
    return path


def where_written(paths: tuple[Path, ...]) -> str:
    """Say in one line where the reports went, for the error stream."""
    return f"{WRITTEN_TO} {', '.join(map(str, paths))}\n"
