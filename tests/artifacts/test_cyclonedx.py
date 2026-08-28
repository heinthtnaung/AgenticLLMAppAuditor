"""The standard-format bill: the recorded scan, minus the parts that vary.

Two things have to hold at once. The file must be byte-identical between two
runs of the same scan, and it must still be valid CycloneDX -- the fields
dropped for the first are all optional, which is what keeps the second true.

The recorded fixture holds only the components, so the fields Syft really emits
around them -- serialNumber, metadata, bom-ref, cpe, syft: properties -- are
put back here.
"""

import copy

from artifacts.cyclonedx import GENERATOR_PROPERTY_PREFIX, to_cyclonedx
from artifacts.sbom import sbom_to_json
from dependency_fixtures import CORPUS_GENERATOR_OUTPUT, corpus_sbom

# The two fields that differ between two runs of the same scan.
SERIAL_NUMBER = "urn:uuid:00000000-0000-4000-8000-000000000001"
OTHER_SERIAL_NUMBER = "urn:uuid:00000000-0000-4000-8000-000000000002"
TIMESTAMP = "2026-08-23T09:00:00Z"
OTHER_TIMESTAMP = "2026-08-23T17:30:00Z"

# The three fields CycloneDX requires of a document; dropping one would make
# the file useless to the tooling it is written for.
SPEC_VERSION = "1.6"
DOCUMENT_VERSION = 1

SYFT_PROPERTIES = [
    {"name": "syft:package:foundBy", "value": "python-installed-package-cataloger"},
    {"name": "syft:location:0:path", "value": "/home/someone/app/requirements.txt"},
]

# A property no generator invented, so it must survive. Only one component
# carries it; the rest have syft: properties alone and must lose the key.
KEPT_PROPERTY = {"name": "cdx:pypi:package:name", "value": "openai"}
PROPERTY_HOLDER = "openai"
ONLY_SYFT_PROPERTIES = "langchain"

# What the recorded scan reports, in the order to_cyclonedx must return.
SORTED_COMPONENTS = [
    ("library", "langchain"),
    ("library", "langchain-litellm"),
    ("library", "openai"),
]


def _syft_component(component: dict) -> dict:
    """Add to one recorded component the fields Syft fills in and this project drops."""
    name, version = component["name"], component.get("version")
    component["bom-ref"] = f"pkg:pypi/{name}@{version}?package-id=9f1c0b2a4d6e8f01"
    component["cpe"] = f"cpe:2.3:a:{name}:{name}:{version}:*:*:*:*:*:*:*"
    if version:
        component["purl"] = f"pkg:pypi/{name}@{version}"
    component["properties"] = list(SYFT_PROPERTIES)
    if name == PROPERTY_HOLDER:
        component["properties"].append(dict(KEPT_PROPERTY))
    return component


def syft_document(serial_number: str = SERIAL_NUMBER, timestamp: str = TIMESTAMP) -> dict:
    """Return the recorded scan as Syft emits it, for the given serial and timestamp."""
    document = copy.deepcopy(CORPUS_GENERATOR_OUTPUT)
    document["bomFormat"] = "CycloneDX"
    document["specVersion"] = SPEC_VERSION
    document["version"] = DOCUMENT_VERSION
    document["serialNumber"] = serial_number
    document["metadata"] = {"timestamp": timestamp, "component": {"type": "file", "name": "app"}}
    document["components"] = [_syft_component(c) for c in document["components"]]
    return document


def other_run() -> dict:
    """Return the same scan as a second run of Syft: new serial number, new timestamp."""
    return syft_document(serial_number=OTHER_SERIAL_NUMBER, timestamp=OTHER_TIMESTAMP)


def component_named(document: dict, name: str) -> dict:
    """Return one component of a CycloneDX document by name."""
    return next(c for c in document["components"] if c["name"] == name)


def test_the_two_recorded_runs_differ_only_in_serial_number_and_timestamp() -> None:
    """Names the exact difference the next test has to neutralise."""
    first, second = syft_document(), other_run()
    differing = sorted(key for key in first if first[key] != second[key])
    assert differing == ["metadata", "serialNumber"]
    assert first["metadata"]["component"] == second["metadata"]["component"]


def test_two_runs_of_the_same_scan_serialise_to_identical_bytes() -> None:
    """Reproducibility: a diff between two runs must show only real change."""
    first = sbom_to_json(to_cyclonedx(syft_document()))
    second = sbom_to_json(to_cyclonedx(other_run()))
    assert first == second


def test_the_serialised_document_carries_no_serial_number_and_no_timestamp() -> None:
    """Either field would make every run differ from the last."""
    text = sbom_to_json(to_cyclonedx(syft_document()))
    assert "serialNumber" not in text
    assert "timestamp" not in text


def test_the_three_fields_the_spec_requires_all_survive() -> None:
    """Drop one and the file is useless to the tooling it is written for."""
    document = syft_document()
    stable = to_cyclonedx(document)
    assert stable["bomFormat"] == "CycloneDX"
    assert stable["specVersion"] == document["specVersion"] == SPEC_VERSION
    assert stable["version"] == DOCUMENT_VERSION


def test_no_component_keeps_its_bom_ref_or_its_cpe() -> None:
    """bom-ref embeds a Syft package-id hash; the cpe is a vendor string Syft invents."""
    for component in to_cyclonedx(syft_document())["components"]:
        assert "bom-ref" not in component, component["name"]
        assert "cpe" not in component, component["name"]


def test_no_generator_property_survives() -> None:
    """A syft: property records how the scan ran, not what the app depends on."""
    for component in to_cyclonedx(syft_document())["components"]:
        for entry in component.get("properties", []):
            assert not entry["name"].startswith(GENERATOR_PROPERTY_PREFIX), entry


def test_a_component_with_only_generator_properties_loses_the_key() -> None:
    """An empty properties list is noise, so the key goes rather than sitting empty."""
    component = component_named(to_cyclonedx(syft_document()), ONLY_SYFT_PROPERTIES)
    assert "properties" not in component


def test_a_property_no_generator_invented_is_kept() -> None:
    """Only syft: properties are dropped; anything else is part of the scan's content."""
    component = component_named(to_cyclonedx(syft_document()), PROPERTY_HOLDER)
    assert component["properties"] == [KEPT_PROPERTY]


def test_the_purl_name_and_version_of_every_component_are_preserved_exactly() -> None:
    """The purl is the identity other tooling joins on, so none of the three may change."""
    document = syft_document()
    expected = {c["name"]: (c.get("purl"), c.get("version")) for c in document["components"]}
    for component in to_cyclonedx(document)["components"]:
        name = component["name"]
        assert (component.get("purl"), component.get("version")) == expected[name], name


def test_components_are_sorted_by_type_then_name_then_version() -> None:
    """Sorted output is what makes the file diffable between two scans."""
    document = to_cyclonedx(syft_document())
    assert [(c["type"], c["name"]) for c in document["components"]] == SORTED_COMPONENTS


def test_the_input_order_of_the_components_cannot_show_through() -> None:
    """Syft's catalogue order is not stable, so it must not reach the file."""
    shuffled = syft_document()
    shuffled["components"].reverse()
    assert sbom_to_json(to_cyclonedx(shuffled)) == sbom_to_json(to_cyclonedx(syft_document()))


def test_the_manifest_file_component_is_dropped() -> None:
    """The generator names it by absolute path, which would describe this machine.

    Every other artifact forbids absolute paths, and a standard bill that only
    reproduces on the machine that made it is not much use to the tooling it
    exists for. Which manifest was read is in sbom.json, relative.
    """
    document = to_cyclonedx(syft_document())
    assert all(c["type"] == "library" for c in document["components"])
    assert not any("/" in c["name"] for c in document["components"])


def test_an_empty_scan_returns_an_empty_component_list() -> None:
    """Nothing found is a valid result, so it must not raise or omit the key."""
    assert to_cyclonedx({}) == {"components": []}


def test_the_scan_it_was_given_is_left_untouched() -> None:
    """A pure function: the caller still holds the scan it passed in."""
    document = syft_document()
    before = copy.deepcopy(document)
    to_cyclonedx(document)
    assert document == before


def test_the_project_bill_lists_more_components_than_the_standard_one() -> None:
    """Why both files exist: sbom.json adds what the manifest declares and the scan missed."""
    project = corpus_sbom()
    standard = to_cyclonedx(syft_document())
    assert len(project["components"]) == 5
    assert len(standard["components"]) == 3
