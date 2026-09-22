"""Syft: the components a directory declares, handed on in this project's terms.

A thin wrapper. It runs the tool, reads the JSON and returns components; nothing
here scores a finding or joins one to an advisory. Syft's own field names stop at
this module, so no later step has to know which tool catalogued the tree.

Syft missing is a normal answer and not a crash: `is_available` lets a caller
report an audit with no components, and say why, rather than fail the run.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from deps.scanner import (
    ScannerFailed,
    as_directory,
    refuse_missing_directory,
    run_json_scanner,
)

SYFT_EXECUTABLE = "syft"
SCAN_SUBCOMMAND = "scan"
DIRECTORY_SCHEME = "dir:"
JSON_FORMAT = ("-o", "syft-json")

# Syft's own field names, spelled out once here and nowhere else in the project.
ARTIFACTS = "artifacts"
ARTIFACT_NAME = "name"
ARTIFACT_VERSION = "version"
ARTIFACT_PURL = "purl"
ARTIFACT_ECOSYSTEM = "type"
ARTIFACT_LOCATIONS = "locations"
LOCATION_PATH = "path"

# Without a name and a purl an artifact identifies nothing and can be joined to
# nothing, so it is refused rather than carried as half a record. A version is
# not on the list: Syft leaves it empty for a component it found but could not
# version, and that is the tool's honest answer, not a broken report.
REQUIRED_ARTIFACT_FIELDS = (ARTIFACT_NAME, ARTIFACT_PURL)

UNNAMED_ARTIFACT = "<unnamed>"


@dataclass(frozen=True)
class Component:
    """One component a directory declares: what it is, which version, and where it was found."""

    name: str
    version: str
    purl: str
    ecosystem: str
    locations: tuple[str, ...]


def is_available() -> bool:
    """Say whether Syft is installed, so a caller can report no components rather than fail."""
    return shutil.which(SYFT_EXECUTABLE) is not None


def scan_directory(directory: str | Path) -> tuple[Component, ...]:
    """Run Syft over a directory and give the components it catalogues."""
    scanned = as_directory(directory)
    refuse_missing_directory(scanned)
    return read_components(run_json_scanner(build_command(scanned)))


def build_command(directory: Path) -> list[str]:
    """Build the Syft command line for one directory."""
    return [
        SYFT_EXECUTABLE,
        SCAN_SUBCOMMAND,
        f"{DIRECTORY_SCHEME}{directory}",
        *JSON_FORMAT,
    ]


def read_components(report: Any) -> tuple[Component, ...]:
    """Read the components out of a parsed Syft report, in a fixed order."""
    components = [read_component(artifact) for artifact in report_artifacts(report)]
    return tuple(sorted(components, key=component_order))


def report_artifacts(report: Any) -> list:
    """Take the artifact list out of a report, refusing a document of another shape."""
    if not isinstance(report, Mapping) or not isinstance(report.get(ARTIFACTS), list):
        raise ScannerFailed(f"A Syft report must be a JSON object carrying an {ARTIFACTS!r} list")
    return report[ARTIFACTS]


def read_component(artifact: Any) -> Component:
    """Translate one Syft artifact into a component of this project's own vocabulary."""
    refuse_unidentified_artifact(artifact)
    return Component(
        name=artifact[ARTIFACT_NAME],
        version=artifact.get(ARTIFACT_VERSION) or "",
        purl=artifact[ARTIFACT_PURL],
        ecosystem=artifact.get(ARTIFACT_ECOSYSTEM) or "",
        locations=read_locations(artifact),
    )


def refuse_unidentified_artifact(artifact: Any) -> None:
    """Refuse an artifact missing what identifies the component it stands for."""
    if not isinstance(artifact, Mapping):
        raise ScannerFailed("A Syft artifact must be a JSON object")
    missing = [field for field in REQUIRED_ARTIFACT_FIELDS if not artifact.get(field)]
    if not missing:
        return
    named = artifact.get(ARTIFACT_NAME) or UNNAMED_ARTIFACT
    raise ScannerFailed(f"Syft artifact {named!r} is missing {', '.join(missing)}")


def read_locations(artifact: Mapping[str, Any]) -> tuple[str, ...]:
    """Give the paths a component was found at, sorted and without repeats."""
    entries = artifact.get(ARTIFACT_LOCATIONS) or []
    paths = {
        entry[LOCATION_PATH]
        for entry in entries
        if isinstance(entry, Mapping) and entry.get(LOCATION_PATH)
    }
    return tuple(sorted(paths))


def component_order(component: Component) -> tuple[str, str, str, tuple[str, ...]]:
    """Order components so two scans over one tree produce identical output."""
    return (component.name, component.version, component.purl, component.locations)
