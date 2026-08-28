"""`VERSION_SOURCES` is a contract, not a comment: every component must use it.

The tuple was declared and then read by nothing, so a typo in one branch of
`version_source_of` would have shipped a value no reader knows. These tests are
what make the vocabulary binding, and they run over the documents the builder
really emits rather than over the constants.
"""

from artifacts.sbom import EXACT_SOURCES, INFERRED, VERSION_SOURCES, build_sbom
from dependency_fixtures import (
    GENERATOR_NAME,
    GENERATOR_VERSION,
    PYPI_MANIFEST,
    corpus_sbom,
    js_sbom,
)
from deps.package_names import PYPI

# The values as they are written into sbom.json. Spelled out rather than
# compared to the module's own constants: that comparison passes through any
# typo, and the string is what a reader of the artifact keys on.
EXPECTED_VERSION_SOURCES = ("pinned", "locked", "inferred", "unconstrained", "unknown")
EXPECTED_EXACT_SOURCES = ("pinned", "locked")

# The sources whose `version` field is kept. `inferred` joins the exact ones
# here and only here: the version is real evidence, it just may not be asserted.
VERSIONED_SOURCES = (*EXACT_SOURCES, INFERRED)

# A package declared with no constraint that the generator still resolved.
# Neither corpus app has one, and without it the retention rule below is never
# exercised: everywhere else an unversioned source had no version to drop.
UNCONSTRAINED_BUT_RESOLVED = build_sbom(
    {"components": [{"type": "library", "name": "widget", "version": "1.2.3"}]},
    {"widget": ""}, GENERATOR_NAME, GENERATOR_VERSION, [PYPI_MANIFEST],
    version_guessing_enabled=True, ecosystem=PYPI,
)

# Every component the three documents emit, so the checks cover both ecosystems.
ALL_COMPONENTS = (corpus_sbom()["components"] + js_sbom()["components"]
                  + UNCONSTRAINED_BUT_RESOLVED["components"])


def test_the_vocabulary_is_the_five_values_the_artifact_writes() -> None:
    """A renamed or mistyped source is a value every downstream reader would miss."""
    assert VERSION_SOURCES == EXPECTED_VERSION_SOURCES


def test_the_exact_sources_are_the_two_that_observed_a_version() -> None:
    """A pin was declared and a lock was resolved; everything else is a guess."""
    assert EXACT_SOURCES == EXPECTED_EXACT_SOURCES


def test_every_exact_source_is_part_of_the_vocabulary() -> None:
    """`EXACT_SOURCES` selects from `VERSION_SOURCES`; it cannot introduce a new one."""
    assert set(EXACT_SOURCES) <= set(VERSION_SOURCES)


def test_every_emitted_version_source_is_in_the_vocabulary() -> None:
    """The enforcement: no component may report a source outside the tuple."""
    for component in ALL_COMPONENTS:
        assert component["version_source"] in VERSION_SOURCES, component


def test_the_fixtures_between_them_exercise_the_whole_vocabulary() -> None:
    """Guards the test above: a check that never sees a value proves nothing about it."""
    emitted = {component["version_source"] for component in ALL_COMPONENTS}
    assert emitted == set(VERSION_SOURCES)


def test_a_version_reaches_a_purl_exactly_when_its_source_is_exact() -> None:
    """The invariant the vocabulary exists for, in both directions at once."""
    for component in ALL_COMPONENTS:
        versioned = component["purl"].endswith(f"@{component['version']}")
        expected = component["version_source"] in EXACT_SOURCES and bool(component["version"])
        assert versioned == expected, component


def test_a_version_is_kept_only_for_a_source_that_observed_one() -> None:
    """`unconstrained` and `unknown` did not observe one, so the field must stay null."""
    for component in ALL_COMPONENTS:
        kept = component["version"] is not None
        assert kept == (component["version_source"] in VERSIONED_SOURCES), component


def test_an_unconstrained_package_drops_a_version_the_generator_resolved() -> None:
    """The case that makes the rule above bite, named so the behaviour is on the record.

    A bare `widget` says nothing about versions, so the document reports none
    even though the generator found 1.2.3. Keeping it would put a version
    against a component whose provenance says no version was established.
    """
    component = UNCONSTRAINED_BUT_RESOLVED["components"][0]
    assert component["version_source"] == "unconstrained"
    assert component["version"] is None
    assert component["purl"] == "pkg:pypi/widget"
