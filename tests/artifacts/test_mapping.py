"""Joining the corpus app's surfaces to the packages they come from.

The counts below are measured from the real fixture, not chosen: they are what
makes a silent change in the join visible.
"""

from artifacts.mapping import (
    FIRST_PARTY,
    STDLIB,
    THIRD_PARTY,
    UNRESOLVED,
    USED_BUT_UNDECLARED,
    build_mapping,
)
from conftest import CORPUS_DIR
from dependency_fixtures import SUPPORT_AGENT, corpus_sbom, corpus_surfaces
from parsing.repo_loader import local_module_names

# Measured on corpus/vuln-app-1-support-agent with its own modules known.
EXPECTED_REASON_COUNTS = {
    THIRD_PARTY: 6,
    STDLIB: 3,
    FIRST_PARTY: 1,
    USED_BUT_UNDECLARED: 1,
    UNRESOLVED: 8,
}
EXPECTED_SURFACE_COUNT = 19


def corpus_mapping() -> dict:
    """Map the corpus app's surfaces, telling the join which modules are its own."""
    local = local_module_names(str(CORPUS_DIR / SUPPORT_AGENT))
    return build_mapping(corpus_surfaces(), corpus_sbom(), local)


def test_every_surface_gets_exactly_one_entry() -> None:
    """A mapping with fewer entries than surfaces has quietly dropped one."""
    surfaces = corpus_surfaces()
    mapping = build_mapping(surfaces, corpus_sbom())
    assert mapping["surface_count"] == len(mapping["entries"]) == len(surfaces)


def test_no_surface_is_mapped_twice() -> None:
    """Surface ids in the mapping are unique, so no surface is counted twice."""
    entries = corpus_mapping()["entries"]
    assert len({entry["surface_id"] for entry in entries}) == len(entries)


def test_the_corpus_app_maps_to_the_measured_reason_counts() -> None:
    """The nineteen surfaces split 6/3/1/1/8 across the five outcomes."""
    assert corpus_mapping()["reason_counts"] == EXPECTED_REASON_COUNTS


def test_the_reason_counts_add_up_to_the_surface_count() -> None:
    """Every surface lands in exactly one reason bucket."""
    mapping = corpus_mapping()
    assert sum(mapping["reason_counts"].values()) == mapping["surface_count"]
    assert mapping["surface_count"] == EXPECTED_SURFACE_COUNT


def test_mapped_and_unmapped_counts_agree_with_the_reasons() -> None:
    """`mapped_count` is the third-party count; the rest are unmapped."""
    mapping = corpus_mapping()
    assert mapping["mapped_count"] == EXPECTED_REASON_COUNTS[THIRD_PARTY]
    assert mapping["unmapped_count"] == mapping["surface_count"] - mapping["mapped_count"]


def test_the_only_undeclared_component_is_pyyaml() -> None:
    """`import yaml` is PyYAML, which the app uses and never declares."""
    assert corpus_mapping()["undeclared_components"] == ["pyyaml"]


def test_a_purl_appears_exactly_when_the_entry_is_third_party() -> None:
    """The join invariant: a purl means a declared package was found, and nothing else.

    A purl on any other reason would key an advisory lookup on a package the
    SBOM never listed.
    """
    for entry in corpus_mapping()["entries"]:
        assert (entry["purl"] is not None) == (entry["reason"] == THIRD_PARTY), entry


def test_every_third_party_entry_names_a_component_in_the_sbom() -> None:
    """A mapped entry points at a component the SBOM really lists."""
    names = {component["name"] for component in corpus_sbom()["components"]}
    for entry in corpus_mapping()["entries"]:
        if entry["reason"] == THIRD_PARTY:
            assert entry["component_name"] in names, entry


def test_entries_are_ordered_by_surface_id() -> None:
    """A fixed order is what makes two runs of the artifact comparable."""
    ids = [entry["surface_id"] for entry in corpus_mapping()["entries"]]
    assert ids == sorted(ids)


def test_an_empty_surface_list_maps_to_an_empty_mapping() -> None:
    """No surfaces is an answer, not an error: zero entries and zero counts."""
    mapping = build_mapping([], corpus_sbom())
    assert mapping["surface_count"] == 0
    assert mapping["entries"] == []
    assert set(mapping["reason_counts"].values()) == {0}
