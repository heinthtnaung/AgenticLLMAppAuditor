"""How this project spells a package's identity, checked against Syft's own.

A PURL is what other supply-chain tooling joins on, so `sbom.json` and
`sbom.cyclonedx.json` cannot sit in one directory naming the same package two
different ways. npm's scope is the case that can differ: the spec requires the
`@` percent-encoded, and the readable spelling is wrong rather than merely
different.

Split from test_package_names.py, which owns the naming and version rules these
purls are built out of.
"""

import pytest

from artifacts.cyclonedx import to_cyclonedx
from artifacts.sbom import PINNED, purl_for
from dependency_fixtures import JS_GENERATOR_SAMPLE, SCOPED_NAME, SCOPED_PURL_NAME
from deps.package_names import NPM, PYPI, exact_version, purl_name


def test_a_purl_percent_encodes_an_npm_scope() -> None:
    """The PURL spec requires the `@` encoded, and the `/` left as the separator."""
    assert purl_name(SCOPED_NAME, NPM) == SCOPED_PURL_NAME


def test_a_purl_leaves_an_unscoped_npm_name_alone() -> None:
    """An unscoped name has nothing to encode, so it must come back untouched."""
    assert purl_name("zod", NPM) == "zod"


def test_only_npm_names_get_a_scope_encoded() -> None:
    """The encoding is npm's rule; a PyPI name is spelled as it is written."""
    assert purl_name(SCOPED_NAME, PYPI) == SCOPED_NAME


@pytest.mark.parametrize("component", JS_GENERATOR_SAMPLE["components"],
                         ids=lambda c: f"{c['name']}@{c['version']}")
def test_a_locally_built_purl_matches_the_generators_own(component: dict) -> None:
    """This project spells a package's identity exactly as Syft does.

    All 80 library components of the real `oss-app-langgraphjs-starter` scan
    were checked out of band: 0 mismatches. The eight recorded here cover every
    shape and keep the check off a machine with Syft installed.
    """
    built = purl_for(component["name"], NPM, component["version"], PINNED)
    assert built == component["purl"]


def test_the_scoped_purl_is_the_encoded_one_not_the_readable_one() -> None:
    """`pkg:npm/@langchain/community@0.3.3` is wrong, not merely a different spelling."""
    scoped = JS_GENERATOR_SAMPLE["components"][0]
    assert scoped["purl"] == f"pkg:npm/{SCOPED_PURL_NAME}@{scoped['version']}"
    assert SCOPED_NAME not in scoped["purl"].removesuffix(f"@{scoped['version']}")


@pytest.mark.parametrize("component", JS_GENERATOR_SAMPLE["components"],
                         ids=lambda c: f"{c['name']}@{c['version']}")
def test_a_generator_resolved_version_is_an_exact_npm_version(component: dict) -> None:
    """Every version the scan resolved is a pin by npm's rule, so it may reach a purl."""
    assert exact_version(component["version"], NPM) == component["version"]


def test_both_bills_state_the_same_identity_for_every_package() -> None:
    """The purl in sbom.cyclonedx.json equals the one this project builds itself.

    Two documents in one artifacts directory naming the same package two ways
    is worse than either being wrong alone, so the agreement is checked on the
    document `to_cyclonedx` really emits, not on the recorded input.
    """
    emitted = to_cyclonedx(JS_GENERATOR_SAMPLE)["components"]
    assert len(emitted) == len(JS_GENERATOR_SAMPLE["components"])
    for component in emitted:
        assert component["purl"] == purl_for(component["name"], NPM,
                                             component["version"], PINNED)
