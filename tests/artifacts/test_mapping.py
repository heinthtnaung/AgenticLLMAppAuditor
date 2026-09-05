"""The whole-document invariants of a mapping: one entry per surface, and no guesses.

These used to be measured on a pinned app whose nineteen surfaces split
6/3/1/1/8 across the five outcomes. That app is gone, so the surface list is
now written here -- chosen to reach all five outcomes at once, which the pinned
one did only by luck. The counts stay literal so a join that quietly dropped a
surface still fails.

What it gives up: the list is the author's own, so it holds no unforeseen
import shape, no oversized module and no framework idiom nobody thought of.
Per-outcome behaviour is `test_mapping_reasons.py`; this file is about the
document as a whole.
"""

from artifacts.mapping import (
    FIRST_PARTY,
    STDLIB,
    THIRD_PARTY,
    UNRESOLVED,
    USED_BUT_UNDECLARED,
    build_mapping,
)
from dependency_fixtures import pypi_sbom
from surface_fixtures import LOCAL_MODULES, PYTHON_SURFACES

# Measured on `PYTHON_SURFACES`, with `utils` known to be the app's own.
EXPECTED_REASON_COUNTS = {
    THIRD_PARTY: 2,
    STDLIB: 1,
    FIRST_PARTY: 1,
    USED_BUT_UNDECLARED: 2,
    UNRESOLVED: 1,
}
EXPECTED_SURFACE_COUNT = 7

# Resolved to a real package that no manifest declares: PyYAML from `yaml`, and
# the npm package the PyPI bill cannot answer for.
EXPECTED_UNDECLARED = ["@langchain/openai", "pyyaml"]


def mapping() -> dict:
    """Map the written surface list against the recorded SBOM."""
    return build_mapping(PYTHON_SURFACES, pypi_sbom(), LOCAL_MODULES)


def test_every_surface_gets_exactly_one_entry() -> None:
    """A mapping with fewer entries than surfaces has quietly dropped one."""
    document = build_mapping(PYTHON_SURFACES, pypi_sbom())
    assert (document["surface_count"] == len(document["entries"])
            == len(PYTHON_SURFACES) == EXPECTED_SURFACE_COUNT)


def test_no_surface_is_mapped_twice() -> None:
    """Surface ids in the mapping are unique, so no surface is counted twice."""
    entries = mapping()["entries"]
    assert len({entry["surface_id"] for entry in entries}) == len(entries)


def test_the_written_surfaces_map_to_the_measured_reason_counts() -> None:
    """The seven surfaces split 2/1/1/2/1, so every outcome has at least one entry."""
    assert mapping()["reason_counts"] == EXPECTED_REASON_COUNTS


def test_the_reason_counts_add_up_to_the_surface_count() -> None:
    """Every surface lands in exactly one reason bucket."""
    document = mapping()
    assert sum(document["reason_counts"].values()) == document["surface_count"]
    assert document["surface_count"] == EXPECTED_SURFACE_COUNT


def test_mapped_and_unmapped_counts_agree_with_the_reasons() -> None:
    """`mapped_count` is the third-party count; the rest are unmapped."""
    document = mapping()
    assert document["mapped_count"] == EXPECTED_REASON_COUNTS[THIRD_PARTY]
    assert document["unmapped_count"] == document["surface_count"] - document["mapped_count"]


def test_the_undeclared_components_are_the_ones_no_manifest_lists() -> None:
    """`import yaml` is PyYAML, which this bill of materials never declares."""
    assert mapping()["undeclared_components"] == EXPECTED_UNDECLARED


def test_a_purl_appears_exactly_when_the_entry_is_third_party() -> None:
    """The join invariant: a purl means a declared package was found, and nothing else.

    A purl on any other reason would key an advisory lookup on a package the
    SBOM never listed.
    """
    for entry in mapping()["entries"]:
        assert (entry["purl"] is not None) == (entry["reason"] == THIRD_PARTY), entry


def test_every_third_party_entry_names_a_component_in_the_sbom() -> None:
    """A mapped entry points at a component the SBOM really lists."""
    names = {component["name"] for component in pypi_sbom()["components"]}
    joined = [e for e in mapping()["entries"] if e["reason"] == THIRD_PARTY]
    assert len(joined) == EXPECTED_REASON_COUNTS[THIRD_PARTY]
    for entry in joined:
        assert entry["component_name"] in names, entry


def test_entries_are_ordered_by_surface_id() -> None:
    """A fixed order is what makes two runs of the artifact comparable."""
    ids = [entry["surface_id"] for entry in mapping()["entries"]]
    assert ids == sorted(ids)


def test_the_order_the_surfaces_arrive_in_does_not_change_the_entries() -> None:
    """File-walk order must not reach the artifact, or two machines would differ."""
    reversed_document = build_mapping(list(reversed(PYTHON_SURFACES)),
                                      pypi_sbom(), LOCAL_MODULES)
    assert reversed_document["entries"] == mapping()["entries"]


def test_an_empty_surface_list_maps_to_an_empty_mapping() -> None:
    """No surfaces is an answer, not an error: zero entries and zero counts."""
    document = build_mapping([], pypi_sbom())
    assert document["surface_count"] == 0
    assert document["entries"] == []
    assert set(document["reason_counts"].values()) == {0}
