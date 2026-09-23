"""The advisory database's own build date: the one check that stops a silent clean report.

Trivy with no database finds nothing and exits 0, which is indistinguishable
from a clean repository. The database's build date is what separates the two,
and a caller is meant to ask before the scan rather than after reading the
report.

The date is the database's own, never the local download time: a stale database
copied to this machine this morning is still stale, and `DownloadedAt` would
call it fresh.
"""

import json
from pathlib import Path
from typing import Any, Mapping

from deps.scanner import as_path

DATABASE_METADATA_PATH = Path.home() / ".cache" / "trivy" / "db" / "metadata.json"

DATABASE_BUILD_DATE = "UpdatedAt"


def database_built_at(metadata_path: str | Path = DATABASE_METADATA_PATH) -> str | None:
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
