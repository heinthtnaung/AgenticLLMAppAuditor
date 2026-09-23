"""The refusals that happen before anything is scanned.

**Trivy with no database finds nothing and exits 0.** That is indistinguishable
from a clean repository, and it is the failure this whole file exists to stop:
by the time a report is written the damage is done, because the report is
believable. So the database is asked for its build date first, and a run that
cannot read one does not start.

Every refusal here is "could not run", which a pipeline must be able to tell
from "found nothing". Conflating the two is how a broken scan passes.
"""

from pathlib import Path

from deps import syft_runner, trivy_runner
from deps.trivy_database import DATABASE_METADATA_PATH, database_built_at


class CannotRun(RuntimeError):
    """The audit could not start, which is not the same as finding nothing."""


def refuse_unrunnable(repository: Path, metadata_path: Path = DATABASE_METADATA_PATH) -> str:
    """Refuse a run that cannot produce a trustworthy report, and give the database's date."""
    refuse_missing_repository(repository)
    refuse_missing_scanners()
    return database_date(metadata_path)


def refuse_missing_repository(repository: Path) -> None:
    """Refuse a path that is not a directory on this machine."""
    if repository.is_dir():
        return
    raise CannotRun(f"{str(repository)!r} is not a directory to audit")


def refuse_missing_scanners() -> None:
    """Refuse a run without the tools, rather than reporting a repository with nothing in it."""
    absent = [
        name
        for name, installed in (
            ("syft", syft_runner.is_available()),
            ("trivy", trivy_runner.is_available()),
        )
        if not installed
    ]
    if absent:
        raise CannotRun(f"{', '.join(absent)} is not installed on this machine")


def database_date(metadata_path: Path) -> str:
    """Give the advisory database's own build date, refusing a scan that would find nothing."""
    built_at = database_built_at(metadata_path)
    if built_at:
        return built_at
    raise CannotRun(
        f"no advisory database build date at {str(metadata_path)!r}; a scan without one "
        "finds nothing and exits 0, which reads exactly like a clean repository"
    )
