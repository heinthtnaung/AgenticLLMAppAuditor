"""The whole join, end to end: build_sbom -> build_mapping -> find_known_advisories.

test_known_advisory.py hand-builds its mapping entries with a versioned purl,
so it proves the check joins correctly and nothing else. It cannot see the seam
this file exists for: the purl those entries carry is *produced* by `sbom.py`,
and it carries a version only where `version_source` is `pinned` or `locked`.
Nothing connected the two, so the document-wide `from_lockfile` defect could
change which advisories the auditor reports without a single test moving.

Both directions matter, and the second is the dangerous one. A component that
loses its versioned purl does not merely lose its findings: `advisories.get`
returns `[]` *and* the purl falls out of `reached`, so it is published in
`advisory_unreached_components` -- a positive claim of unreachability, quoted
in the report and in the VEX document. A false negative that asserts itself.

Everything here is built in the test. The advisory ids and the component are
the ones `advisory_fixtures` transcribed from a real Trivy run, so no test
needs Trivy, Syft, or an audited tree on disk.
"""

from advisory_fixtures import (
    FIRST_ADVISORY,
    JS_COMPONENT_PURL,
    SECOND_ADVISORY,
    js_advisories,
)
from artifacts.finding import Finding
from artifacts.mapping import THIRD_PARTY, build_mapping
from artifacts.sbom import INFERRED, LOCKED, build_sbom
from artifacts.surface import TOOL_CALL, Surface
from checks.known_advisory import (
    find_known_advisories,
    unreached_components,
)
from checks.supply_chain import surface_fields
from dependency_fixtures import (
    GENERATOR_NAME,
    GENERATOR_VERSION,
    JS_MANIFESTS,
    NPM_MANIFEST,
    YARN_LOCK,
    located_in,
)
from deps.package_names import NPM
from parsing.languages import TYPESCRIPT

# The vulnerable component, exactly as the advisory index keys it.
COMPONENT = "@langchain/community"
VERSION = "0.3.3"
CONSTRAINT = "^0.3.3"
BARE_PURL = "pkg:npm/%40langchain/community"

# The two places the generator can say it read that version from. Only the
# second is a resolution; the first is the range in package.json.
MANIFEST_LOCATION = f"/{NPM_MANIFEST}"
LOCKFILE_LOCATION = f"/{YARN_LOCK}"

# One tool call importing the vulnerable package, so the finding has a file and
# a line a grading key could score.
SURFACE = Surface(TOOL_CALL, "TavilySearchResults", "src/agent.ts", 9, TYPESCRIPT,
                  "tool", f"{COMPONENT}/tools/tavily_search")
FIELDS = surface_fields([SURFACE])

BOTH_ADVISORIES = sorted([FIRST_ADVISORY, SECOND_ADVISORY])


def sbom_locating_the_component(location: str) -> dict:
    """Build the npm SBOM for one declared package the generator read from `location`."""
    reported = {"type": "library", "name": COMPONENT, "version": VERSION,
                "properties": located_in(location)}
    return build_sbom({"components": [reported]}, {COMPONENT: CONSTRAINT},
                      GENERATOR_NAME, GENERATOR_VERSION, JS_MANIFESTS,
                      version_guessing_enabled=True, ecosystem=NPM)


def mapping_for(location: str) -> dict:
    """Map the one surface against the SBOM built for that generator location."""
    return build_mapping([SURFACE], sbom_locating_the_component(location))


def findings_for(location: str) -> list[Finding]:
    """Run the whole chain and return the advisory findings it produces."""
    return find_known_advisories(mapping_for(location), js_advisories(), FIELDS)


# --- A version the lockfile resolved: the advisory is reported ---------------

def test_a_lockfile_located_component_reaches_the_advisory_index() -> None:
    """The link itself: the purl sbom.py built is the key the advisories are filed under."""
    entry = mapping_for(LOCKFILE_LOCATION)["entries"][0]
    assert entry["reason"] == THIRD_PARTY
    assert entry["purl"] == JS_COMPONENT_PURL


def test_that_component_is_locked_rather_than_guessed() -> None:
    """Guards the test above: the purl carries a version only because it was locked."""
    component = sbom_locating_the_component(LOCKFILE_LOCATION)["components"][0]
    assert component["version_source"] == LOCKED


def test_both_advisories_on_it_become_findings() -> None:
    """One finding per (surface, component, advisory), out of the real chain this time."""
    found = findings_for(LOCKFILE_LOCATION)
    assert sorted(finding.advisory_id for finding in found) == BOTH_ADVISORIES


def test_each_finding_is_anchored_on_the_surface_that_reached_it() -> None:
    """The file and line come through the whole chain, not from a hand-built entry."""
    for finding in findings_for(LOCKFILE_LOCATION):
        assert (finding.file, finding.line) == ("src/agent.ts", 9)
        assert finding.surface_id == SURFACE.id


def test_a_reached_component_is_not_also_published_as_unreached() -> None:
    """The two halves cannot both be true, and only the join can prove they are not."""
    unreached = unreached_components(mapping_for(LOCKFILE_LOCATION), js_advisories())
    assert unreached == []


# --- A version the generator guessed: no advisory may be claimed -------------

def test_a_manifest_located_component_gets_a_bare_purl() -> None:
    """Same package, same version, same lockfile on disk -- only the evidence moved."""
    entry = mapping_for(MANIFEST_LOCATION)["entries"][0]
    assert entry["reason"] == THIRD_PARTY
    assert entry["purl"] == BARE_PURL


def test_that_component_is_inferred_rather_than_locked() -> None:
    """`^0.3.3` admits 0.3.99, so the version sbom.py holds is evidence, not a fact."""
    component = sbom_locating_the_component(MANIFEST_LOCATION)["components"][0]
    assert component["version_source"] == INFERRED


def test_a_guessed_version_claims_no_advisory() -> None:
    """The mirror, and the reason the purl rule exists: no version, no CVE claim.

    Under the document-wide flag this component was `locked` purely because
    yarn.lock existed, so both advisories above were reported against a version
    the app may never install.
    """
    assert findings_for(MANIFEST_LOCATION) == []


def test_the_guessed_component_is_then_counted_as_unreached() -> None:
    """The published cost of that silence, pinned so a change to it is deliberate.

    This is not a second opinion about reachability: the surface plainly reaches
    `@langchain/community`. It is that `unreached_components` is keyed on the
    versioned purl, so a join that could not name a version reads as no join at
    all. Asserted because the report and the VEX document both quote it.
    """
    unreached = unreached_components(mapping_for(MANIFEST_LOCATION), js_advisories())
    assert [item["purl"] for item in unreached] == [JS_COMPONENT_PURL]


def test_the_two_builds_differ_only_in_the_file_the_generator_named() -> None:
    """Guards every pair above: the version, the constraint and the lockfile all match."""
    locked_document = sbom_locating_the_component(LOCKFILE_LOCATION)
    guessed_document = sbom_locating_the_component(MANIFEST_LOCATION)
    assert locked_document["scanned_manifests"] == guessed_document["scanned_manifests"]
    assert YARN_LOCK in locked_document["scanned_manifests"]
    locked, guessed = locked_document["components"][0], guessed_document["components"][0]
    assert locked["version"] == guessed["version"] == VERSION
    assert locked["version_constraint"] == guessed["version_constraint"] == CONSTRAINT
