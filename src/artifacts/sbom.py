"""Builds a deterministic SBOM from a generator's output and the app's manifest.

Pure: takes what the generator found and what the manifest declares, returns the
document. Storing the generator's own output is not an option -- it carries a
random identifier, a timestamp and absolute paths, so two runs would differ.
"""

import json

from deps.requirements_parser import normalise_name

SCHEMA_VERSION = 1

PYPI = "pypi"
NPM = "npm"
ECOSYSTEMS = (PYPI, NPM)

# How a component's version was arrived at. Never read `version` without it.
PINNED = "pinned"
INFERRED = "inferred"
UNCONSTRAINED = "unconstrained"
UNKNOWN = "unknown"
VERSION_SOURCES = (PINNED, INFERRED, UNCONSTRAINED, UNKNOWN)

EXACT_PIN = "=="
LIBRARY = "library"

# A pin containing either of these is a range, not a version: `==1.4.*` admits
# 1.4.99, and a comma joins several constraints.
RANGE_MARKERS = ("*", ",")


def pinned_version(constraint: str) -> str:
    """Return the version an exact pin names, or "" if the pin is really a range.

    `==1.4.*` looks pinned but admits 1.4.99, so treating it as a version would
    put a range in the purl and let an advisory lookup claim a vulnerability the
    app may not have.
    """
    text = constraint[len(EXACT_PIN):].strip()
    if not text or any(marker in text for marker in RANGE_MARKERS):
        return ""
    return text


def version_source_of(constraint: str, version: str | None) -> str:
    """Say how much a version can be trusted, given the constraint that produced it.

    An `==` that pinned_version refuses -- `==1.4.*`, `==1.2.3,!=1.2.4` -- is a
    range wearing a pin's syntax, so it must not report as pinned here either.
    The two functions have to agree, or a range reaches the purl.
    """
    if constraint.startswith(EXACT_PIN) and pinned_version(constraint):
        return PINNED
    if not constraint:
        return UNCONSTRAINED
    return INFERRED if version else UNKNOWN


def purl_for(name: str, ecosystem: str, version: str | None, source: str) -> str:
    """Build a package URL, carrying a version only when that version is a fact.

    A range like ~=0.3.25 admits 0.3.99, so a purl built from a guess would let
    any purl-keyed advisory lookup claim a vulnerability the app may not have.
    """
    base = f"pkg:{ecosystem}/{name}"
    return f"{base}@{version}" if source == PINNED and version else base


def _component(name: str, constraint: str | None, declared: bool, version: str | None,
               declared_in: str | None, tool_reported: bool, ecosystem: str = PYPI) -> dict:
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
    text = constraint or ""
    exact = pinned_version(text) if text.startswith(EXACT_PIN) else ""
    version = exact or version
    source = PINNED if exact else version_source_of(text, version)
    if source == PINNED and not version:
        source = UNKNOWN
    return {
        "name": name,
        "ecosystem": ecosystem,
        "version": version if source in (PINNED, INFERRED) else None,
        "version_source": source,
        "version_constraint": constraint or None,
        "purl": purl_for(name, ecosystem, version, source),
        "declared": declared,
        "tool_reported": tool_reported,
        "declared_in": declared_in,
    }


def _reported_versions(generator_output: dict) -> dict[str, str]:
    """Map each library the generator reported to the version it gave it."""
    return {
        normalise_name(c["name"]): c.get("version")
        for c in generator_output.get("components", [])
        if c.get("type") == LIBRARY and c.get("name")
    }


def build_sbom(generator_output: dict, declared: dict[str, str],
               generator_name: str, generator_version: str,
               scanned_manifests: list[str], version_guessing_enabled: bool,
               ecosystem: str = PYPI) -> dict:
    """Return the SBOM: every declared package, plus anything the generator found.

    One ecosystem per call. Only Python manifests are read today; an npm app
    needs its own manifest reader before its components could be labelled
    correctly, and mislabelling them would break every join downstream.
    """
    if ecosystem not in ECOSYSTEMS:
        raise ValueError(f"unknown ecosystem {ecosystem!r}; expected one of {ECOSYSTEMS}")
    reported = _reported_versions(generator_output)
    manifest = scanned_manifests[0] if scanned_manifests else None
    components = [
        _component(name, declared.get(name), name in declared, reported.get(name),
                   manifest if name in declared else None,
                   name in reported, ecosystem)
        for name in sorted(set(declared) | set(reported))
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
