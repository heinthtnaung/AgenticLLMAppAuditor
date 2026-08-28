"""One package installed at several versions, and which manifest declared it.

A lockfile legitimately resolves the same name more than once: the JS corpus app
has `langsmith` at three versions and `@langchain/openai` at two. Each installed
copy is its own supply-chain fact, so each gets its own record -- a name-keyed
dict would keep the last and silently drop the rest.
"""

import pytest

from artifacts.sbom import build_sbom
from dependency_fixtures import (
    GENERATOR_NAME,
    GENERATOR_VERSION,
    JS_DECLARED,
    JS_MANIFESTS,
    NPM_MANIFEST,
    POETRY_LOCK,
    PYPI_MANIFEST,
    YARN_LOCK,
    js_sbom,
)
from deps.package_names import LOCKFILE_NAMES, NPM, NPM_LOCKFILES, PYPI_LOCKFILES

# Measured on the recorded sample of the JS corpus app's lockfile scan.
LANGSMITH_VERSIONS = ["0.1.48", "0.1.55", "0.1.61"]
OPENAI_VERSIONS = ["0.3.0", "0.3.2"]

# Five distinct names across the eight sampled components, plus the four
# declared packages the sample does not cover.
EXPECTED_SAMPLE_COMPONENT_COUNT = 12


# One declared package, so the built document has exactly one record to read
# `declared_in` off. Which ecosystem it is does not enter into the question.
ONE_DECLARED = {"zod": "^3.23.8"}


def declaring_manifest(scanned_manifests: list[str]) -> str | None:
    """Ask a built SBOM which of the files it read is the one that declares.

    Through `build_sbom` rather than the private helper behind it: the artifact
    field is the contract, and a test reaching past it would keep passing after
    the builder stopped calling the helper at all.
    """
    document = build_sbom({}, ONE_DECLARED, GENERATOR_NAME, GENERATOR_VERSION,
                          scanned_manifests, version_guessing_enabled=True, ecosystem=NPM)
    return document["components"][0]["declared_in"]


def records_named(document: dict, name: str) -> list[dict]:
    """Return every component record the document holds for one package name."""
    return [c for c in document["components"] if c["name"] == name]


def test_three_installed_versions_give_three_records() -> None:
    """langsmith is in the lockfile three times, so the SBOM lists it three times."""
    assert len(records_named(js_sbom(), "langsmith")) == len(LANGSMITH_VERSIONS)


def test_each_installed_version_is_recorded_separately() -> None:
    """All three versions survive; a name-keyed dict would have kept one."""
    versions = [c["version"] for c in records_named(js_sbom(), "langsmith")]
    assert versions == LANGSMITH_VERSIONS


def test_each_duplicate_record_carries_its_own_purl() -> None:
    """The records are separate supply-chain facts, so each keys its own lookup."""
    purls = [c["purl"] for c in records_named(js_sbom(), "langsmith")]
    assert purls == [f"pkg:npm/langsmith@{version}" for version in LANGSMITH_VERSIONS]


def test_a_scoped_name_duplicates_the_same_way() -> None:
    """@langchain/openai is installed twice, and the scope encoding survives both."""
    records = records_named(js_sbom(), "@langchain/openai")
    assert [c["version"] for c in records] == OPENAI_VERSIONS
    assert [c["purl"] for c in records] == [
        f"pkg:npm/%40langchain/openai@{version}" for version in OPENAI_VERSIONS
    ]


def test_every_duplicate_record_stays_declared_by_the_manifest() -> None:
    """One declaration produced several installs; all of them are still declared."""
    for record in records_named(js_sbom(), "langsmith"):
        assert record["declared"] is True
        assert record["declared_in"] == NPM_MANIFEST


def test_the_component_count_counts_records_not_names() -> None:
    """A count keyed on names would understate the tree while looking complete."""
    document = js_sbom()
    assert document["component_count"] == len(document["components"])
    assert document["component_count"] == EXPECTED_SAMPLE_COMPONENT_COUNT
    assert document["component_count"] > len(JS_DECLARED)


def test_duplicate_records_are_ordered_by_version() -> None:
    """A fixed order within a name is what keeps two runs of sbom.json comparable."""
    keys = [(c["ecosystem"], c["name"], c["version"] or "") for c in js_sbom()["components"]]
    assert keys == sorted(keys)


def test_a_declared_package_the_lockfile_never_resolved_still_gets_one_record() -> None:
    """No installed copy is still one fact: the app declared it."""
    assert len(records_named(js_sbom(), "typescript")) == 1


def test_the_declaring_manifest_is_the_one_that_is_not_a_lockfile() -> None:
    """package.json declares; yarn.lock only pins what the declaration resolved to."""
    assert declaring_manifest(JS_MANIFESTS) == NPM_MANIFEST


def test_the_declaring_manifest_ignores_the_order_it_was_given() -> None:
    """The answer is which file it is, never which position it arrived in."""
    assert declaring_manifest([YARN_LOCK, NPM_MANIFEST]) == NPM_MANIFEST


def test_lockfiles_alone_declare_nothing() -> None:
    """A lockfile records what was installed, so there is no declaration to cite."""
    assert declaring_manifest([YARN_LOCK]) is None


def test_no_manifest_at_all_declares_nothing() -> None:
    """Nothing was read, so `declared_in` has nothing to say and must not guess."""
    assert declaring_manifest([]) is None


@pytest.mark.parametrize("lockfile", sorted(LOCKFILE_NAMES))
def test_every_known_lockfile_is_treated_as_one(lockfile: str) -> None:
    """Both ecosystems' lockfiles are recognised, or one would be read as declaring."""
    assert declaring_manifest([lockfile]) is None


def test_the_two_lockfile_lists_make_up_the_whole_set() -> None:
    """`LOCKFILE_NAMES` is the union of the ecosystems' lists, with nothing dropped."""
    assert LOCKFILE_NAMES == frozenset(PYPI_LOCKFILES + NPM_LOCKFILES)


def test_the_two_lockfiles_the_tests_name_are_ones_the_owner_lists() -> None:
    """dependency_fixtures spells these two out; package_names owns whether they count.

    Without this, renaming one in the source would leave the fixture naming a
    file nothing treats as a lockfile, and `locked` would quietly stop happening.
    """
    assert POETRY_LOCK in PYPI_LOCKFILES
    assert YARN_LOCK in NPM_LOCKFILES


def test_building_an_sbom_from_mixed_manifests_is_refused() -> None:
    """One document holds one ecosystem, so two declarations mean the caller mixed them."""
    with pytest.raises(ValueError):
        build_sbom({}, {}, GENERATOR_NAME, GENERATOR_VERSION,
                   [NPM_MANIFEST, PYPI_MANIFEST],
                   version_guessing_enabled=True, ecosystem=NPM)


def test_the_refusal_names_both_manifests() -> None:
    """The message says what was mixed, so the caller can see which repo did it."""
    with pytest.raises(ValueError) as error:
        declaring_manifest([NPM_MANIFEST, PYPI_MANIFEST])
    assert NPM_MANIFEST in str(error.value)
    assert PYPI_MANIFEST in str(error.value)
