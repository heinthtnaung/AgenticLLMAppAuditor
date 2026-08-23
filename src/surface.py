"""Data model for a single LLM surface found in an audited repository.

Identity is (file, line, kind, name) — `detail` is descriptive only, so two
records differing just in `detail` are the same surface and are deduplicated.
"""

import json
from dataclasses import asdict, dataclass

# The four kinds of LLM surface Phase 1 detects.
PROMPT_TEMPLATE = "PROMPT_TEMPLATE"
AGENT_DEF = "AGENT_DEF"
TOOL_CALL = "TOOL_CALL"
DATA_SOURCE = "DATA_SOURCE"

SURFACE_KINDS = (PROMPT_TEMPLATE, AGENT_DEF, TOOL_CALL, DATA_SOURCE)

# Artifact schema version. Bump it whenever a field is added or renamed.
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Surface:
    """One LLM surface: what kind it is, what it is called, and where it lives."""

    kind: str
    name: str
    file: str
    line: int
    detail: str
    module: str = ""

    def __post_init__(self) -> None:
        """Reject a surface that a later phase could not act on."""
        if self.kind not in SURFACE_KINDS:
            raise ValueError(f"unknown surface kind {self.kind!r}; expected one of {SURFACE_KINDS}")
        if not self.name:
            raise ValueError("surface name must not be empty")
        if not self.file:
            raise ValueError("surface file must not be empty")
        if not _is_repo_relative_posix(self.file):
            raise ValueError(f"surface file must be a repo-relative posix path, got {self.file!r}")
        if self.line < 1:
            raise ValueError(f"surface line must be 1 or greater, got {self.line}")

    @property
    def id(self) -> str:
        """Stable cross-phase handle, derived from the surface itself, never its position."""
        return f"{self.file}:{self.line}:{self.kind}:{self.name}"


def _is_repo_relative_posix(file: str) -> bool:
    """Say whether a path is repo-relative with forward slashes, so output is machine-independent."""
    if file.startswith("/") or "\\" in file:
        return False
    return ":" not in file.split("/")[0]


def sort_key(surface: Surface) -> tuple[str, int, str, str]:
    """Order surfaces so the same repository always produces the same output."""
    return (surface.file, surface.line, surface.kind, surface.name)


def deduplicate(surfaces: list[Surface]) -> list[Surface]:
    """Return one surface per identity, in stable order."""
    unique: dict[tuple[str, int, str, str], Surface] = {}
    for surface in sorted(surfaces, key=sort_key):
        unique.setdefault(sort_key(surface), surface)
    return list(unique.values())


def surfaces_to_json(surfaces: list[Surface]) -> str:
    """Serialise surfaces to the stable surfaces.json format."""
    ordered = deduplicate(surfaces)
    records = [{**asdict(surface), "id": surface.id} for surface in ordered]
    document = {
        "schema_version": SCHEMA_VERSION,
        "surface_count": len(records),
        "surfaces": records,
    }
    return json.dumps(document, indent=2, sort_keys=True) + "\n"
