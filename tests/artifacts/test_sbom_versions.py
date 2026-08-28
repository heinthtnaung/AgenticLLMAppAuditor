"""When a version may appear in a purl, and when saying it would be a guess.

A purl is what an advisory lookup is keyed on. `~=0.3.25` admits 0.3.99 and
`==1.4.*` admits 1.4.99, so putting either in a purl lets a lookup claim a
vulnerability the app may not have. Only an exact pin is a fact.
"""

from artifacts.sbom import (
    INFERRED,
    PINNED,
    UNCONSTRAINED,
    build_sbom,
    purl_for,
)
from deps.package_names import PYPI, exact_version
from dependency_fixtures import (
    CORPUS_DECLARED,
    GENERATOR_NAME,
    GENERATOR_VERSION,
    PYPI_MANIFEST,
    corpus_sbom,
)

# A generator that found nothing, for the cases about what the manifest alone says.
NO_GENERATOR_OUTPUT: dict = {"components": []}


def build_one(constraint: str, reported_version: str | None = None) -> dict:
    """Build the SBOM component for a single declared package."""
    components = []
    if reported_version is not None:
        components = [{"type": "library", "name": "widget", "version": reported_version}]
    document = build_sbom({"components": components}, {"widget": constraint},
                          GENERATOR_NAME, GENERATOR_VERSION, [PYPI_MANIFEST],
                          version_guessing_enabled=True, ecosystem=PYPI)
    return document["components"][0]


def test_an_exact_pin_carries_its_version_into_the_purl() -> None:
    """`langchain-litellm==0.2.0` names one version, so the purl may state it."""
    assert purl_for("langchain-litellm", "pypi", "0.2.0", PINNED) == (
        "pkg:pypi/langchain-litellm@0.2.0"
    )


def test_a_compatible_release_range_leaves_the_purl_bare() -> None:
    """`langchain~=0.3.25` admits 0.3.99, so 0.3.25 must not be asserted as the version."""
    assert purl_for("langchain", "pypi", "0.3.25", INFERRED) == "pkg:pypi/langchain"


def test_an_unconstrained_package_leaves_the_purl_bare() -> None:
    """A package declared with no constraint has no version to state."""
    assert purl_for("streamlit", "pypi", None, UNCONSTRAINED) == "pkg:pypi/streamlit"


def test_every_pinned_component_states_its_version_in_its_purl() -> None:
    """Direction one: a pinned component's purl ends in `@<version>`, never bare."""
    pinned = [c for c in corpus_sbom()["components"] if c["version_source"] == PINNED]
    assert pinned, "the corpus app declares an exact pin; without one this proves nothing"
    for component in pinned:
        assert component["purl"] == f"pkg:pypi/{component['name']}@{component['version']}"


def test_no_unpinned_component_states_a_version_in_its_purl() -> None:
    """Direction two: everything else has a bare purl, so dropping all versions fails too."""
    unpinned = [c for c in corpus_sbom()["components"] if c["version_source"] != PINNED]
    assert len(unpinned) == 4, "the corpus app has four unpinned packages"
    for component in unpinned:
        assert component["purl"] == f"pkg:pypi/{component['name']}"


def test_an_inferred_version_is_still_recorded_outside_the_purl() -> None:
    """A generator-reported version is kept in `version`; only the purl refuses it.

    Dropping it would lose real evidence, which is why the purl check above
    cannot be satisfied by emitting no versions at all.
    """
    langchain = next(c for c in corpus_sbom()["components"] if c["name"] == "langchain")
    assert (langchain["version"], langchain["version_source"]) == ("0.3.25", INFERRED)


def test_exact_version_reads_an_exact_pin() -> None:
    """`==1.2.3` names exactly one version, so that version is returned."""
    assert exact_version("==1.2.3", PYPI) == "1.2.3"


def test_exact_version_refuses_a_wildcard_pin() -> None:
    """`==1.4.*` looks pinned but admits 1.4.99, so it names no version."""
    assert exact_version("==1.4.*", PYPI) == ""


def test_exact_version_refuses_several_constraints_at_once() -> None:
    """`==1.2.3,!=1.2.4` is a set of constraints, not a single version."""
    assert exact_version("==1.2.3,!=1.2.4", PYPI) == ""


def test_exact_version_refuses_an_empty_pin() -> None:
    """`==` with nothing after it names no version, and must not return `==`."""
    assert exact_version("==", PYPI) == ""


def test_a_wildcard_pin_alone_reaches_no_purl_version() -> None:
    """A wildcard pin with nothing to confirm it leaves the purl bare."""
    component = build_one("==1.4.*")
    assert component["version"] is None
    assert component["purl"] == "pkg:pypi/widget"


def test_a_wildcard_pin_never_reaches_a_purl_version() -> None:
    """A wildcard pin stays a range even when the generator reports a version.

    `==1.4.*` admits 1.4.99, so labelling it `pinned` and keying a purl on one
    version contradicts `exact_version`, which refuses the same string.
    """
    component = build_one("==1.4.*", "1.4.99")
    assert component["version_source"] != PINNED
    assert component["purl"] == "pkg:pypi/widget"


def test_an_exact_pin_beats_a_generator_reporting_something_else() -> None:
    """The manifest is what the app declares; a generator saying 9.9.9 reports another fact."""
    component = build_one("==1.2.3", "9.9.9")
    assert (component["version"], component["purl"]) == ("1.2.3", "pkg:pypi/widget@1.2.3")


def test_an_exact_pin_survives_a_generator_that_reports_nothing() -> None:
    """A package the generator missed keeps the version its manifest pins."""
    component = build_one("==1.2.3")
    assert component["version_source"] == PINNED
    assert component["purl"] == "pkg:pypi/widget@1.2.3"
    assert component["tool_reported"] is False


def test_the_corpus_manifest_declares_one_exact_pin() -> None:
    """The fixture data holds one pin, two ranges and two bare names, so every path runs."""
    exact = [name for name, text in CORPUS_DECLARED.items() if text.startswith("==")]
    ranges = [name for name, text in CORPUS_DECLARED.items() if text.startswith("~=")]
    assert exact == ["langchain-litellm"]
    assert ranges == ["langchain", "openai"]
