"""Building the corpus app's SBOM from what the generator found and what it declares.

The generator reported three of the five declared packages. Listing only three
would report the app as smaller than it is, so the manifest decides membership
and the generator only contributes versions.
"""

from artifacts.sbom import LIBRARY, build_sbom
from deps.package_names import PYPI
from dependency_fixtures import (
    CORPUS_DECLARED,
    CORPUS_GENERATOR_OUTPUT,
    DROPPED_BY_THE_TOOL,
    GENERATOR_NAME,
    GENERATOR_VERSION,
    corpus_sbom,
)
from deps.requirements_parser import MANIFEST_NAME

# What Syft really reported for the corpus app.
REPORTED_BY_THE_TOOL = ("langchain", "langchain-litellm", "openai")


def component_named(document: dict, name: str) -> dict:
    """Return one component of a built SBOM by name."""
    return next(c for c in document["components"] if c["name"] == name)


def test_all_five_declared_packages_are_present() -> None:
    """The manifest declares five, so five appear even though the generator found three."""
    names = [component["name"] for component in corpus_sbom()["components"]]
    assert names == sorted(CORPUS_DECLARED)


def test_the_generator_reported_fewer_than_the_manifest_declares() -> None:
    """The fixture really is the interesting case: three reported against five declared."""
    libraries = [c for c in CORPUS_GENERATOR_OUTPUT["components"] if c["type"] == LIBRARY]
    assert len(libraries) == 3 < len(CORPUS_DECLARED)


def test_a_package_the_generator_missed_is_still_declared() -> None:
    """streamlit and langchain-community are declared, and the SBOM must say so."""
    document = corpus_sbom()
    for name in DROPPED_BY_THE_TOOL:
        assert component_named(document, name)["declared"] is True, name


def test_a_package_the_generator_missed_says_the_generator_missed_it() -> None:
    """`tool_reported: false` is how a reader tells a gap in the tool from a gap in the app."""
    document = corpus_sbom()
    for name in DROPPED_BY_THE_TOOL:
        assert component_named(document, name)["tool_reported"] is False, name


def test_a_package_the_generator_missed_has_no_invented_version() -> None:
    """No version was observed and none is pinned, so the version stays null."""
    document = corpus_sbom()
    for name in DROPPED_BY_THE_TOOL:
        component = component_named(document, name)
        assert component["version"] is None, name
        assert component["version_source"] == "unconstrained", name


def test_a_reported_package_carries_the_reported_version() -> None:
    """What the generator observed reaches the document, so its output is really read."""
    document = corpus_sbom()
    versions = {name: component_named(document, name)["version"]
                for name in REPORTED_BY_THE_TOOL}
    assert versions == {"langchain": "0.3.25", "langchain-litellm": "0.2.0",
                        "openai": "1.78.0"}


def test_the_component_count_matches_the_component_list() -> None:
    """A count that disagrees with the list would make every downstream total wrong."""
    document = corpus_sbom()
    assert document["component_count"] == len(document["components"]) == 5


def test_components_are_sorted_by_ecosystem_then_name() -> None:
    """A fixed order is what lets two runs of sbom.json be compared."""
    keys = [(c["ecosystem"], c["name"]) for c in corpus_sbom()["components"]]
    assert keys == sorted(keys)


def test_the_scanned_manifest_is_recorded() -> None:
    """The document says which manifest it read, so its membership can be checked."""
    assert corpus_sbom()["scanned_manifests"] == [MANIFEST_NAME]


def test_the_generator_is_named_and_versioned() -> None:
    """Evidence needs its provenance: which tool produced it, at which version."""
    document = corpus_sbom()
    assert document["generator_name"] == GENERATOR_NAME
    assert document["generator_version"] == GENERATOR_VERSION


def test_a_non_library_component_is_ignored() -> None:
    """Syft reports the manifest itself as a `file` component, which is not a package.

    Its name is an absolute path, so taking it would put this machine's
    directory layout into the artifact.
    """
    names = [component["name"] for component in corpus_sbom()["components"]]
    assert not any(name.startswith("/") for name in names)
    assert MANIFEST_NAME not in names


def test_the_recorded_generator_output_really_holds_a_non_library_entry() -> None:
    """Guards the test above: the fixture contains the `file` component it ignores."""
    types = [component["type"] for component in CORPUS_GENERATOR_OUTPUT["components"]]
    assert "file" in types


def test_a_package_only_the_generator_found_is_listed_as_undeclared() -> None:
    """A package present but never declared is the finding, so it must not be dropped."""
    generator_output = {"components": [{"type": LIBRARY, "name": "requests",
                                        "version": "2.32.3"}]}
    document = build_sbom(generator_output, {}, GENERATOR_NAME, GENERATOR_VERSION,
                          [MANIFEST_NAME],
                          version_guessing_enabled=True, ecosystem=PYPI)
    requests = component_named(document, "requests")
    assert requests["declared"] is False
    assert requests["declared_in"] is None
    assert requests["tool_reported"] is True


def test_an_empty_manifest_and_empty_generator_output_give_an_empty_sbom() -> None:
    """An app with no dependencies is an answer, not an error."""
    document = build_sbom({}, {}, GENERATOR_NAME, GENERATOR_VERSION, [],
                          version_guessing_enabled=True, ecosystem=PYPI)
    assert document["component_count"] == 0
    assert document["components"] == []
