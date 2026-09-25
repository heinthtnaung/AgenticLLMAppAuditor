"""The advisory database's own build date: the one check that stops a silent clean report.

Trivy with no database finds nothing and exits 0, which is indistinguishable
from a clean repository. The database's build date is what separates the two,
and a caller is meant to ask before the scan rather than after reading the
report.

The date is the database's own, never the local download time: a stale database
copied to this machine this morning is still stale, and `DownloadedAt` would
call it fresh.

**The database dated is the database scanned, by construction.** Trivy finds
its cache from, in order -- measured on Trivy 0.74 -- `--cache-dir`,
`TRIVY_CACHE_DIR`, a `cache.dir` in a `trivy.yaml` where it runs,
`$XDG_CACHE_HOME/trivy`, and `~/.cache/trivy`. Reading one of those here while
Trivy settled on another would date one database and scan a different one. So
the directory is resolved once, from the environment in that order, and the
scan is handed it as `--cache-dir`, which outranks every other source -- a
`trivy.yaml` included, which this therefore never reads.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from deps.scanner import as_path

DATABASE_BUILD_DATE = "UpdatedAt"
CACHE_VARIABLE = "TRIVY_CACHE_DIR"
XDG_CACHE_VARIABLE = "XDG_CACHE_HOME"
HOME_VARIABLE = "HOME"
TRIVY_FOLDER = "trivy"
HOME_CACHE_FOLDER = ".cache"
METADATA_WITHIN_CACHE = Path("db") / "metadata.json"


@dataclass(frozen=True)
class DatedDatabase:
    """The Trivy cache a run scans with, and the build date of the database in it."""

    cache: Path
    built_at: str


def trivy_cache_directory(environment: Mapping[str, str]) -> Path:
    """Find the cache directory Trivy would use, from the environment in Trivy's own order."""
    named = environment.get(CACHE_VARIABLE)
    if named:
        return Path(named).absolute()
    xdg = environment.get(XDG_CACHE_VARIABLE)
    if xdg:
        return xdg_cache_directory(xdg)
    home = environment.get(HOME_VARIABLE)
    if not home:
        raise ValueError(
            f"no {CACHE_VARIABLE}, {XDG_CACHE_VARIABLE} or {HOME_VARIABLE} is set, so there is no "
            "Trivy cache to find the advisory database in"
        )
    return Path(home) / HOME_CACHE_FOLDER / TRIVY_FOLDER


def xdg_cache_directory(xdg: str) -> Path:
    """Give Trivy's cache under XDG_CACHE_HOME, refusing a relative one Trivy would not use."""
    # Measured: given a relative XDG_CACHE_HOME, Trivy falls back to a temporary
    # directory, so there is no one cache to date and scan with.
    if not Path(xdg).is_absolute():
        raise ValueError(
            f"{XDG_CACHE_VARIABLE} is {xdg!r}, which is relative, and Trivy then keeps its "
            f"cache in a temporary directory; make it absolute or set {CACHE_VARIABLE}"
        )
    return Path(xdg) / TRIVY_FOLDER


def metadata_of(cache: Path) -> Path:
    """Give where the database in a Trivy cache records its build date."""
    return cache / METADATA_WITHIN_CACHE


def database_built_at(metadata_path: str | Path) -> str | None:
    """Give the database's build date as it wrote it, or None when there is none to read."""
    metadata = read_metadata(as_path(metadata_path, "A database metadata path"))
    if not isinstance(metadata, Mapping):
        return None
    built_at = metadata.get(DATABASE_BUILD_DATE)
    if not isinstance(built_at, str) or not built_at.strip():
        return None
    return built_at


def read_metadata(metadata_path: Path) -> Any:
    """Read the database's metadata file, answering None every way it can fail."""
    # A third-party file on the audit path: absent, unopenable, or not the JSON it
    # claims, none of it may crash a run whose findings are already correct.
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
