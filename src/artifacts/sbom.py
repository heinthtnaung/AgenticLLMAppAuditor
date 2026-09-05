"""Builds a deterministic SBOM from a generator's output and the app's manifest.

Pure: takes what the generator found and what the manifest declares, returns the
document. Storing the generator's own output is not an option -- it carries a
random identifier, a timestamp and absolute paths, so two runs would differ.
"""

import json

from deps.package_names import (
    LOCKFILE_NAMES,
    is_lockfile_path,
    base_purl,
    check_ecosystem,
    exact_version,
    normalise_name,
)

SCHEMA_VERSION = 3

# How a component's version was arrived at. Never read `version` without it.
PINNED = "pinned"
LOCKED = "locked"

# How the generator spells "I read this component from this file": a property
# named `syft:location:<n>:path`. Matched by its ends so the index is free.
LOCATION_PREFIX = "syft:location:"
LOCATION_SUFFIX = ":path"
INFERRED = "inferred"
UNCONSTRAINED = "unconstrained"
UNKNOWN = "unknown"
VERSION_SOURCES = (PINNED, LOCKED, INFERRED, UNCONSTRAINED, UNKNOWN)

# The two sources whose version is a fact rather than a guess, so only these
# may reach a purl. See docs/SCHEMAS.md for why the distinction is structural.
EXACT_SOURCES = (PINNED, LOCKED)

# The sources that carry a version at all. `unconstrained` is in here because a
# bare declaration the generator did resolve has evidence worth reporting -- it
# just is not a fact about what the app asked for, so it stays out of the purl.
# `unknown` is the one source meaning a constraint was present and no version
# was ever established.
VERSIONED_SOURCES = (*EXACT_SOURCES, INFERRED, UNCONSTRAINED)

LIBRARY = "library"


def version_source_of(constraint: str, version: str | None, ecosystem: str,
                      from_lockfile: bool = False) -> str:
    """Say how much a version can be trusted, given the constraint that produced it.

    A constraint wearing a pin's syntax without pinning -- `==1.4.*`,
    `==1.2.3,!=1.2.4` -- must not report as pinned here either, or a range
    reaches the purl. `exact_version` owns that judgement for both ecosystems.

    `from_lockfile` is what the caller read, never which ecosystem it is. Keying
    it on the ecosystem would mislabel a Python app shipping a poetry.lock;
    keying it on "the generator reported something" would relabel every guessed
    version as a fact, which is the one outcome this vocabulary exists to stop.
    """
    if exact_version(constraint, ecosystem):
        return PINNED
    if from_lockfile and version:
        return LOCKED
    if not constraint:
        return UNCONSTRAINED
    return INFERRED if version else UNKNOWN


def purl_for(name: str, ecosystem: str, version: str | None, source: str) -> str:
    """Build a package URL, carrying a version only when that version is a fact.

    A range like ~=0.3.25 admits 0.3.99, so a purl built from a guess would let
    any purl-keyed advisory lookup claim a vulnerability the app may not have.
    """
    base = base_purl(name, ecosystem)
    return f"{base}@{version}" if source in EXACT_SOURCES and version else base


def _component(name: str, constraint: str | None, declared: bool, version: str | None,
               declared_in: str | None, tool_reported: bool, ecosystem: str,
               from_lockfile: bool) -> dict:
    """Build one component record.

    An exact pin is taken from the manifest, not from the generator. The
    manifest is what the app declares; a generator reporting something else is
    reporting a different fact, and preferring it would let the purl assert a
    version the app never asked for.

    `declared` says whether a manifest names the package. `declared_in` says
    which one. They are separate because a package can be declared by a
    manifest whose path was not recorded, and reporting that as undeclared
    would invent a supply-chain finding.
    """
    check_ecosystem(ecosystem)
    text = constraint or ""
    exact = exact_version(text, ecosystem)
    version = exact or version
    source = version_source_of(text, version, ecosystem, from_lockfile)
    return {
        "name": name,
        "ecosystem": ecosystem,
        "version": version if source in VERSIONED_SOURCES else None,
        "version_source": source,
        "version_constraint": constraint or None,
        "purl": purl_for(name, ecosystem, version, source),
        "declared": declared,
        "tool_reported": tool_reported,
        "declared_in": declared_in,
    }


def _reported_versions(generator_output: dict, ecosystem: str) -> dict[str, list[str | None]]:
    """Map each library the generator reported to every version it reported for it.

    A list, not one version: a lockfile legitimately holds one package at
    several versions -- this project's own JS fixture has `langsmith` at three
    -- and keying by name alone would keep the last and silently drop the rest.
    """
    found: dict[str, list[str | None]] = {}
    for component in generator_output.get("components", []):
        if component.get("type") != LIBRARY or not component.get("name"):
            continue
        found.setdefault(normalise_name(component["name"], ecosystem), []).append(
            component.get("version"))
    return {name: sorted(versions, key=lambda v: v or "") for name, versions in found.items()}


def _lockfile_pinned(generator_output: dict, ecosystem: str) -> set[tuple[str, str | None]]:
    """The (name, version) pairs the generator found in a lockfile rather than a manifest.

    Per component, because "a lockfile exists in this directory" says nothing
    about where any one version came from. The generator already records the
    file it read each component from, so this reads that evidence rather than
    re-parsing the lockfile or trusting the directory listing.
    """
    pinned: set[tuple[str, str | None]] = set()
    for component in generator_output.get("components", []):
        if component.get("type") != LIBRARY or not component.get("name"):
            continue
        if any(_is_location_of_a_lockfile(prop) for prop in component.get("properties", [])):
            pinned.add((normalise_name(component["name"], ecosystem), component.get("version")))
    return pinned


def _is_location_of_a_lockfile(prop: dict) -> bool:
    """Say whether one generator property records a location, and that it is a lockfile."""
    name = prop.get("name", "")
    return (name.startswith(LOCATION_PREFIX) and name.endswith(LOCATION_SUFFIX)
            and is_lockfile_path(prop.get("value", "")))


def _declaring_manifest(scanned_manifests: list[str]) -> str | None:
    """Return the manifest that declares dependencies, as opposed to a lockfile that pins them.

    Derived rather than passed in, so it can never disagree with
    `scanned_manifests`. One document holds one ecosystem, so at most one
    manifest declares; more than one is not supported yet.
    """
    declaring = sorted(m for m in scanned_manifests if m not in LOCKFILE_NAMES)
    if len(declaring) > 1:
        raise ValueError(f"expected one declaring manifest, got {declaring}")
    return declaring[0] if declaring else None


def build_sbom(generator_output: dict, declared: dict[str, str],
               generator_name: str, generator_version: str,
               scanned_manifests: list[str], version_guessing_enabled: bool,
               ecosystem: str) -> dict:
    """Return the SBOM: every declared package, plus anything the generator found.

    One ecosystem per call, and one record per (name, version) rather than per
    name -- a lockfile can hold the same package at several versions, and each
    installed copy is its own supply-chain fact.
    """
    check_ecosystem(ecosystem)
    reported = _reported_versions(generator_output, ecosystem)
    manifest = _declaring_manifest(scanned_manifests)
    locked = _lockfile_pinned(generator_output, ecosystem)
    components = [
        _component(name, declared.get(name), declared=name in declared, version=version,
                   declared_in=manifest if name in declared else None,
                   tool_reported=name in reported, ecosystem=ecosystem,
                   from_lockfile=(name, version) in locked)
        for name in sorted(set(declared) | set(reported))
        for version in reported.get(name) or [None]
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generator_name": generator_name,
        "generator_version": generator_version,
        "version_guessing_enabled": version_guessing_enabled,
        "scanned_manifests": sorted(scanned_manifests),
        "component_count": len(components),
        "components": sorted(components,
                             key=lambda c: (c["ecosystem"], c["name"], c["version"] or "")),
    }


def sbom_to_json(document: dict) -> str:
    """Serialise the SBOM to its stable on-disk form."""
    return json.dumps(document, indent=2, sort_keys=True) + "\n"
