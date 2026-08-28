"""Which ecosystem an SBOM describes, and what happens when nobody says.

One ecosystem per document: `express` and `express` on PyPI would be different
packages, so a document that mixes them cannot be joined against safely.
"""

import pytest
from artifacts.sbom import build_sbom
from deps.package_names import ECOSYSTEMS, NPM, PYPI
from dependency_fixtures import GENERATOR_NAME, GENERATOR_VERSION
from deps.requirements_parser import MANIFEST_NAME


def build_declared(constraint: str, ecosystem: str = PYPI,
                   scanned_manifests: list[str] | None = None) -> dict:
    """Build the SBOM component for one declared package in the given ecosystem."""
    manifests = [MANIFEST_NAME] if scanned_manifests is None else scanned_manifests
    document = build_sbom({}, {"widget": constraint}, GENERATOR_NAME,
                          GENERATOR_VERSION, manifests,
                          version_guessing_enabled=True, ecosystem=ecosystem)
    return document["components"][0]


def test_no_scanned_manifest_does_not_raise() -> None:
    """A declared package with no recorded manifest path is still a package."""
    assert build_declared("==1.2.3", scanned_manifests=[])["name"] == "widget"


def test_no_scanned_manifest_leaves_declared_in_unset() -> None:
    """`declared_in` says which manifest; with none recorded there is nothing to say."""
    assert build_declared("==1.2.3", scanned_manifests=[])["declared_in"] is None


def test_no_scanned_manifest_still_reports_the_package_as_declared() -> None:
    """`declared` and `declared_in` are separate facts.

    Reading an unrecorded path as "undeclared" would invent a supply-chain
    finding for a package the app names in its manifest.
    """
    assert build_declared("==1.2.3", scanned_manifests=[])["declared"] is True


def test_a_scanned_manifest_is_recorded_against_each_declared_package() -> None:
    """When the path is known, every declared component names it."""
    assert build_declared("==1.2.3")["declared_in"] == MANIFEST_NAME


def test_an_unknown_ecosystem_is_rejected() -> None:
    """A misspelled ecosystem must fail loudly, not produce unjoinable purls."""
    with pytest.raises(ValueError):
        build_sbom({}, {}, GENERATOR_NAME, GENERATOR_VERSION, [],
                   version_guessing_enabled=True, ecosystem="maven")


def test_the_ecosystem_error_names_the_allowed_values() -> None:
    """The message tells the reader what to write instead."""
    with pytest.raises(ValueError) as error:
        build_sbom({}, {}, GENERATOR_NAME, GENERATOR_VERSION, [],
                   version_guessing_enabled=True, ecosystem="maven")
    message = str(error.value)
    assert "maven" in message
    for ecosystem in ECOSYSTEMS:
        assert ecosystem in message


def test_the_default_ecosystem_is_pypi() -> None:
    """Only Python manifests are read today, so PyPI is the default."""
    assert build_declared("==1.2.3")["ecosystem"] == PYPI


def test_npm_reaches_the_ecosystem_field() -> None:
    """A component records the ecosystem it was built for."""
    assert build_declared("==4.19.2", NPM)["ecosystem"] == NPM


def test_npm_reaches_the_purl() -> None:
    """The purl carries the ecosystem too, since that is what a lookup keys on.

    npm spells an exact pin as a bare version; `==4.19.2` is PyPI syntax and
    means nothing there, so it must not be read as a pin.
    """
    assert build_declared("4.19.2", NPM)["purl"] == "pkg:npm/widget@4.19.2"
    assert build_declared("==4.19.2", NPM)["purl"] == "pkg:npm/widget"
