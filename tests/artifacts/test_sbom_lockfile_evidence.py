"""`locked` is decided per component, from where the generator read it.

The bug this file exists for was live until 2026-09-05. `build_sbom` computed
`from_lockfile` once for the whole document -- "is a lockfile named in
`scanned_manifests`?" -- and handed that one boolean to every component. So the
mere *presence* of yarn.lock relabelled every component that had a version as
`locked`, including versions the generator merely guessed from a range. `LOCKED`
is in `EXACT_SOURCES`, so each of those gained a **versioned purl**, and that
purl is the key `known_advisory` joins CVEs on: a guessed version could attract
an advisory filed against a version the app may never install.

Measured before the fix, with nothing changed but whether the file existed:

    ["package.json"]              -> inferred  pkg:npm/guessed-pkg
    ["package.json","yarn.lock"]  -> locked    pkg:npm/guessed-pkg@9.9.9

Every case below builds the whole document, because the defect lived in how the
builder derived the flag, not in `version_source_of`, which was always correct
about the boolean it was given. test_sbom_locked.py owns that half.
"""

from artifacts.sbom import INFERRED, LOCKED, build_sbom
from dependency_fixtures import (
    GENERATOR_NAME,
    GENERATOR_VERSION,
    NPM_MANIFEST,
    YARN_LOCK,
    located_in,
)
from deps.package_names import NPM

# One npm package the manifest constrains with a range, so the version below is
# the generator's resolution and never the app's own declaration. The name says
# what the test is about, because a purl carrying it is the defect itself.
PACKAGE = "guessed-pkg"
CONSTRAINT = "^9.0.0"
VERSION = "9.9.9"
DECLARED = {PACKAGE: CONSTRAINT}

BARE_PURL = f"pkg:npm/{PACKAGE}"
VERSIONED_PURL = f"{BARE_PURL}@{VERSION}"

# The two manifest sets, spelled once. The lockfile is *present* in both the
# defect's case and the fixed one; only the location evidence differs.
MANIFEST_ONLY = (NPM_MANIFEST,)
MANIFEST_AND_LOCKFILE = (NPM_MANIFEST, YARN_LOCK)

# The three places the generator can say it read the component from. The nested
# one is a monorepo's workspace lockfile, which `is_lockfile_path` must match
# by basename rather than by equality with "/yarn.lock".
MANIFEST_LOCATION = f"/{NPM_MANIFEST}"
LOCKFILE_LOCATION = f"/{YARN_LOCK}"
NESTED_LOCKFILE_LOCATION = f"/packages/a/{YARN_LOCK}"


def component_located_in(location: str | None,
                         manifests: tuple[str, ...] = MANIFEST_AND_LOCKFILE) -> dict:
    """Build the one-component SBOM for a package the generator read from `location`."""
    reported = {"type": "library", "name": PACKAGE, "version": VERSION}
    if location:
        reported["properties"] = located_in(location)
    document = build_sbom({"components": [reported]}, DECLARED, GENERATOR_NAME,
                          GENERATOR_VERSION, list(manifests),
                          version_guessing_enabled=True, ecosystem=NPM)
    return document["components"][0]


def test_a_version_located_in_the_manifest_is_inferred_despite_a_lockfile() -> None:
    """The regression: yarn.lock is present, and a version read out of package.json
    is still a guess.

    Nothing but the file's existence changed under the old rule, and that was
    enough to relabel this component `locked`.
    """
    component = component_located_in(MANIFEST_LOCATION)
    assert component["version_source"] == INFERRED


def test_that_guessed_version_never_reaches_the_purl() -> None:
    """The consequence that mattered: a bare purl cannot key an advisory lookup by version."""
    assert component_located_in(MANIFEST_LOCATION)["purl"] == BARE_PURL


def test_the_guessed_version_is_still_reported_as_evidence() -> None:
    """`inferred` keeps the version; it is the purl, not the field, that must not state it."""
    assert component_located_in(MANIFEST_LOCATION)["version"] == VERSION


def test_a_version_located_in_the_lockfile_is_locked() -> None:
    """Same manifests, same version: only the file the generator read it from moved."""
    component = component_located_in(LOCKFILE_LOCATION)
    assert component["version_source"] == LOCKED
    assert component["purl"] == VERSIONED_PURL


def test_a_version_located_in_a_nested_lockfile_is_locked_too() -> None:
    """A monorepo writes /packages/a/yarn.lock, and that is still a lockfile."""
    component = component_located_in(NESTED_LOCKFILE_LOCATION)
    assert component["version_source"] == LOCKED
    assert component["purl"] == VERSIONED_PURL


def test_a_component_with_no_location_at_all_is_inferred() -> None:
    """No evidence is not evidence of a lockfile, however many lockfiles were scanned."""
    component = component_located_in(None)
    assert component["version_source"] == INFERRED
    assert component["purl"] == BARE_PURL


def test_removing_the_lockfile_changes_nothing_for_a_manifest_located_version() -> None:
    """The old rule made these two differ; under the fixed one the file's presence is inert."""
    with_lockfile = component_located_in(MANIFEST_LOCATION, MANIFEST_AND_LOCKFILE)
    without_lockfile = component_located_in(MANIFEST_LOCATION, MANIFEST_ONLY)
    assert with_lockfile == without_lockfile
    assert with_lockfile["version_source"] == INFERRED


def test_one_locked_component_does_not_lock_the_one_beside_it() -> None:
    """Per component, not per document: the two differ inside a single SBOM.

    The old flag was one boolean for the whole build, so this is the shape it
    could not express at all.
    """
    reported = [
        {"type": "library", "name": PACKAGE, "version": VERSION,
         "properties": located_in(MANIFEST_LOCATION)},
        {"type": "library", "name": "pinned-pkg", "version": "1.0.0",
         "properties": located_in(LOCKFILE_LOCATION)},
    ]
    document = build_sbom({"components": reported},
                          {PACKAGE: CONSTRAINT, "pinned-pkg": "^1.0.0"},
                          GENERATOR_NAME, GENERATOR_VERSION, list(MANIFEST_AND_LOCKFILE),
                          version_guessing_enabled=True, ecosystem=NPM)
    sources = {c["name"]: c["version_source"] for c in document["components"]}
    assert sources == {PACKAGE: INFERRED, "pinned-pkg": LOCKED}


def component_carrying(property_name: str, value: str) -> dict:
    """Build the one-component SBOM for a package carrying one arbitrary property."""
    reported = {"type": "library", "name": PACKAGE, "version": VERSION,
                "properties": [{"name": property_name, "value": value}]}
    document = build_sbom({"components": [reported]}, DECLARED, GENERATOR_NAME,
                          GENERATOR_VERSION, list(MANIFEST_AND_LOCKFILE),
                          version_guessing_enabled=True, ecosystem=NPM)
    return document["components"][0]


def test_a_location_property_that_is_not_a_path_is_ignored() -> None:
    """Syft writes other `syft:location:<n>:` keys; only the `:path` one names a file."""
    component = component_carrying("syft:location:0:layerID", LOCKFILE_LOCATION)
    assert component["version_source"] == INFERRED


def test_a_non_generator_property_holding_a_lockfile_path_is_ignored() -> None:
    """The prefix is checked too, so an unrelated property naming a file cannot lock."""
    component = component_carrying("cdx:npm:package:path", LOCKFILE_LOCATION)
    assert component["version_source"] == INFERRED
