"""Reading a Syft report: what it catalogued, and what nothing can be joined to.

Syft's own field names stop here, so no later step has to know which tool
catalogued a tree. Nothing in this file runs anything; `deps.syft_runner` does
that and hands the parsed document over.

**An artifact with no purl is reported, not refused.** Some things Syft
catalogues have no package identity by nature -- a workflow calling
`./local-action` or `./.github/workflows/reusable.yml` is one, and no advisory
database could ever carry a purl for it. Refusing the whole scan over an
artifact that could never be joined turns a non-issue into total failure, and
larger repositories do this constantly. So they are collected and handed on to
be counted and named: nothing is silently dropped, which was the point of
refusing in the first place. This is decided by the missing purl and never by
the artifact's type, because the next cataloguer will have a different one.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from deps.scanner import ScannerFailed

# Syft's own field names, spelled out once here and nowhere else in the project.
ARTIFACTS = "artifacts"
ARTIFACT_NAME = "name"
ARTIFACT_VERSION = "version"
ARTIFACT_PURL = "purl"
ARTIFACT_ECOSYSTEM = "type"
ARTIFACT_LOCATIONS = "locations"
LOCATION_PATH = "path"

# A version is not required: Syft leaves it empty for a component it found but
# could not version, and that is the tool's honest answer, not a broken report.
UNNAMED_ARTIFACT = "<unnamed>"


@dataclass(frozen=True)
class UnidentifiedArtifact:
    """Something Syft catalogued that carries no purl, so nothing could ever join to it."""

    name: str
    ecosystem: str
    locations: tuple[str, ...]


@dataclass(frozen=True)
class Component:
    """One component a directory declares: what it is, which version, and where it was found."""

    name: str
    version: str
    purl: str
    ecosystem: str
    locations: tuple[str, ...]


@dataclass(frozen=True)
class Catalogue:
    """What Syft found: what can be joined to an advisory, and what cannot."""

    components: tuple[Component, ...]
    unidentified: tuple[UnidentifiedArtifact, ...]


def read_catalogue(report: Any) -> Catalogue:
    """Read a parsed Syft report into what can be joined and what cannot, in a fixed order."""
    entries = [read_artifact(artifact) for artifact in report_artifacts(report)]
    catalogued = Catalogue(
        components=tuple(
            sorted((one for one in entries if isinstance(one, Component)), key=component_order)
        ),
        unidentified=tuple(
            sorted(
                (one for one in entries if isinstance(one, UnidentifiedArtifact)),
                key=artifact_order,
            )
        ),
    )
    refuse_a_catalogue_of_nothing_joinable(catalogued)
    return catalogued


def refuse_a_catalogue_of_nothing_joinable(catalogued: Catalogue) -> None:
    """Refuse a scan that identified nothing at all, which is a cataloguer that failed."""
    # A repository with no packages catalogues nothing and is not this. This is
    # artifacts found and not one of them identified, which is Syft going wrong
    # rather than a repository being empty, and it must not read as a clean scan.
    if catalogued.components or not catalogued.unidentified:
        return
    found = len(catalogued.unidentified)
    raise ScannerFailed(
        f"Syft catalogued {found} artifact{'' if found == 1 else 's'} and identified none of them"
    )


def report_artifacts(report: Any) -> list:
    """Take the artifact list out of a report, refusing a document of another shape."""
    if not isinstance(report, Mapping) or not isinstance(report.get(ARTIFACTS), list):
        raise ScannerFailed(f"A Syft report must be a JSON object carrying an {ARTIFACTS!r} list")
    return report[ARTIFACTS]


def read_artifact(artifact: Any) -> Component | UnidentifiedArtifact:
    """Translate one Syft artifact into a component, or into something nothing can join."""
    if not isinstance(artifact, Mapping):
        raise ScannerFailed("A Syft artifact must be a JSON object")
    if not artifact.get(ARTIFACT_PURL):
        return UnidentifiedArtifact(
            name=artifact.get(ARTIFACT_NAME) or UNNAMED_ARTIFACT,
            ecosystem=artifact.get(ARTIFACT_ECOSYSTEM) or "",
            locations=read_locations(artifact),
        )
    return Component(
        name=artifact.get(ARTIFACT_NAME) or UNNAMED_ARTIFACT,
        version=artifact.get(ARTIFACT_VERSION) or "",
        purl=artifact[ARTIFACT_PURL],
        ecosystem=artifact.get(ARTIFACT_ECOSYSTEM) or "",
        locations=read_locations(artifact),
    )


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


def artifact_order(artifact: UnidentifiedArtifact) -> tuple[str, str, tuple[str, ...]]:
    """Order unidentified artifacts so two scans over one tree produce identical output."""
    return (artifact.name, artifact.ecosystem, artifact.locations)
