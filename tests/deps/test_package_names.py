"""When two package names are one package, and when an exact version is a fact.

PyPI and npm genuinely disagree. PEP 503 collapses `-`, `_` and `.` to one `-`,
so `lodash.merge` and `lodash-merge` are one PyPI package; on npm they are two
different real packages. The same split runs through versions: npm's exact pin
is a bare version, and `==1.2.3` is PyPI syntax that means nothing there.

The purls those names and versions end up in are in test_package_purls.py.
"""

from typing import Callable

import pytest

from dependency_fixtures import SCOPED_NAME
from deps.package_names import (
    ECOSYSTEMS,
    NPM,
    PYPI,
    base_purl,
    check_ecosystem,
    exact_version,
    normalise_name,
    purl_name,
)

# The load-bearing pair: two different real npm packages that PEP 503 would
# merge into one. No recorded scan has a dotted npm name -- the JS one
# reports 80 library components and not one of them contains a `.` -- so this
# case is synthetic, and it is the reason npm normalisation only lowercases.
DOTTED_NPM_NAME = "lodash.merge"
HYPHENATED_NPM_NAME = "lodash-merge"

# A real scoped npm package whose name PEP 503 would rewrite to
# `@types/babel-core`, which is a different, real package.
UNDERSCORED_SCOPED_NAME = "@types/babel__core"

UNKNOWN_ECOSYSTEM = "maven"


@pytest.mark.parametrize("ecosystem", ECOSYSTEMS)
def test_every_registered_ecosystem_is_accepted(ecosystem: str) -> None:
    """The two ecosystems this project has rules for pass the check."""
    assert check_ecosystem(ecosystem) is None


def test_an_unknown_ecosystem_is_rejected() -> None:
    """An unregistered ecosystem must fail loudly rather than be given PyPI's rules."""
    with pytest.raises(ValueError):
        check_ecosystem(UNKNOWN_ECOSYSTEM)


def test_the_ecosystem_error_names_the_allowed_values() -> None:
    """The message tells the reader what was wrong and what to write instead."""
    with pytest.raises(ValueError) as error:
        check_ecosystem(UNKNOWN_ECOSYSTEM)
    message = str(error.value)
    assert UNKNOWN_ECOSYSTEM in message
    for ecosystem in ECOSYSTEMS:
        assert ecosystem in message


@pytest.mark.parametrize("function", [normalise_name, exact_version, purl_name, base_purl])
def test_no_rule_guesses_at_an_unknown_ecosystem(function: Callable[[str, str], str]) -> None:
    """Every rule refuses an ecosystem it has no rules for; none silently assumes PyPI."""
    with pytest.raises(ValueError):
        function("anything", UNKNOWN_ECOSYSTEM)


def test_pypi_collapses_a_dotted_name_onto_a_hyphenated_one() -> None:
    """PEP 503 makes `lodash.merge` and `lodash-merge` one PyPI package."""
    assert normalise_name(DOTTED_NPM_NAME, PYPI) == HYPHENATED_NPM_NAME
    assert normalise_name(HYPHENATED_NPM_NAME, PYPI) == HYPHENATED_NPM_NAME


def test_npm_keeps_a_dotted_name_distinct_from_a_hyphenated_one() -> None:
    """On npm those are two different real packages, so the dot must survive.

    Synthetic: no recorded scan has a dotted npm name, but applying PEP 503
    here would join a vulnerability to the wrong package.
    """
    assert normalise_name(DOTTED_NPM_NAME, NPM) == DOTTED_NPM_NAME
    assert normalise_name(DOTTED_NPM_NAME, NPM) != normalise_name(HYPHENATED_NPM_NAME, NPM)


def test_npm_keeps_a_double_underscore_in_a_scoped_name() -> None:
    """`@types/babel__core` is a real package; PEP 503 would rename it to another one."""
    assert normalise_name(UNDERSCORED_SCOPED_NAME, NPM) == UNDERSCORED_SCOPED_NAME
    assert normalise_name(UNDERSCORED_SCOPED_NAME, PYPI) == "@types/babel-core"


def test_npm_lowercases() -> None:
    """npm names are case-insensitive, so the one thing both ecosystems do is lowercase."""
    assert normalise_name("Zod", NPM) == "zod"


def test_normalising_an_npm_scope_leaves_its_at_sign_alone() -> None:
    """Normalisation is about identity; percent-encoding belongs to `purl_name`."""
    assert normalise_name(SCOPED_NAME, NPM) == SCOPED_NAME


@pytest.mark.parametrize("constraint,expected", [
    ("1.2.3", "1.2.3"),
    ("=1.2.3", "1.2.3"),
    ("1.2.3-beta.1", "1.2.3-beta.1"),
])
def test_an_npm_exact_pin_names_its_version(constraint: str, expected: str) -> None:
    """npm pins with a bare version, optionally behind a single `=`."""
    assert exact_version(constraint, NPM) == expected


@pytest.mark.parametrize("constraint", [
    "^1.2.3", "~1.2.3", "1.2.x", "*", ">=1 <2", "latest", "file:../x",
    "npm:a@1.2.3", "==1.2.3",
])
def test_an_npm_range_names_no_version(constraint: str) -> None:
    """Everything else names a set of versions, so none may reach a purl.

    `==1.2.3` is in the list on purpose: it is PyPI syntax, npm has no `==`
    operator, and reading it as a pin asserts a version nothing declared.
    """
    assert exact_version(constraint, NPM) == ""


@pytest.mark.parametrize("constraint", ["~=0.3.25", ">=1.2.3", "1.2.3"])
def test_a_pypi_constraint_without_a_double_equals_names_no_version(constraint: str) -> None:
    """PyPI pins only with `==`; a bare version there is a requirement, not a pin."""
    assert exact_version(constraint, PYPI) == ""


def test_the_same_text_means_different_things_in_each_ecosystem() -> None:
    """One string, two answers -- which is why `exact_version` requires an ecosystem."""
    assert exact_version("1.2.3", PYPI) == ""
    assert exact_version("1.2.3", NPM) == "1.2.3"
    assert exact_version("==1.2.3", PYPI) == "1.2.3"
    assert exact_version("==1.2.3", NPM) == ""
