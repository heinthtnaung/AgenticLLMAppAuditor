"""Ecosystem rules for package names, exact versions, and PURL spelling.

Neutral ground on purpose: the SBOM builder and the import matcher both need
these, and neither is the natural owner. Every rule here belongs to the
ecosystem, not to this project — PyPI and npm genuinely disagree about when two
names are the same package, and collapsing them would join packages that are
not the same package.
"""

import re
from pathlib import PurePosixPath

PYPI = "pypi"
NPM = "npm"
ECOSYSTEMS = (PYPI, NPM)

# PyPI's exact pin is `==`; npm writes a bare version and uses no operator.
PYPI_EXACT_PIN = "=="
NPM_EXACT_PIN = "="

# A PyPI pin containing either of these is a range wearing a pin's syntax:
# `==1.4.*` admits 1.4.99, and a comma joins several constraints.
PYPI_RANGE_MARKERS = ("*", ",")

# What a lockfile resolves to: a full three-part version, with an optional
# prerelease or build suffix. Anything else npm accepts -- `^1.2`, `1.2.x`,
# `>=1 <2`, `latest`, `file:../x`, a git URL -- names a set, not a version.
NPM_EXACT_VERSION = re.compile(r"^\d+\.\d+\.\d+([-+][0-9A-Za-z.-]+)?$")

# Files that record what was actually installed, as opposed to what the app
# asked for. The list spans ecosystems because the *rule* is ecosystem-neutral:
# `locked` is assigned from "a lockfile was read", never from the ecosystem. The
# Python path does not read one yet -- `requirements_parser.manifests_present`
# reports only the manifest -- so today only npm reaches `locked` in practice.
PYPI_LOCKFILES = ("Pipfile.lock", "poetry.lock")
NPM_LOCKFILES = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock")
LOCKFILE_NAMES = frozenset(PYPI_LOCKFILES + NPM_LOCKFILES)


def is_lockfile_path(path: str) -> bool:
    """Say whether a generator-reported location is a lockfile, by its file name.

    By basename, not by equality: the generator writes a scan-root-relative
    `/yarn.lock`, and a monorepo writes `/packages/a/yarn.lock`.
    """
    return PurePosixPath(path).name in LOCKFILE_NAMES

# npm scopes start with `@`, which a PURL must percent-encode.
NPM_SCOPE_PREFIX = "@"
NPM_SCOPE_ENCODED = "%40"


def check_ecosystem(ecosystem: str) -> None:
    """Reject an ecosystem this project has no rules for, rather than guessing PyPI's."""
    if ecosystem not in ECOSYSTEMS:
        raise ValueError(f"unknown ecosystem {ecosystem!r}; expected one of {ECOSYSTEMS}")


def normalise_name(name: str, ecosystem: str) -> str:
    """Return the ecosystem's canonical form of a package name, so every join is equality.

    PyPI (PEP 503) lowercases and collapses runs of `-`, `_` and `.` to one `-`,
    so `Foo.Bar` and `foo-bar` are one package. npm only lowercases: there,
    `lodash.merge` and `lodash-merge` are two different packages, and
    collapsing them would join the wrong one.
    """
    check_ecosystem(ecosystem)
    if ecosystem == PYPI:
        return re.sub(r"[-_.]+", "-", name).lower()
    return name.lower()


def exact_version(constraint: str, ecosystem: str) -> str:
    """Return the version a constraint pins exactly, or "" if it names a range.

    Syntax only: this says whether the *text* is an exact version, not whether
    the source that wrote it is authoritative. Who is allowed to pin is
    `sbom.py`'s decision.
    """
    check_ecosystem(ecosystem)
    text = constraint.strip()
    if ecosystem == PYPI:
        if not text.startswith(PYPI_EXACT_PIN):
            return ""
        rest = text[len(PYPI_EXACT_PIN):].strip()
        return "" if not rest or any(m in rest for m in PYPI_RANGE_MARKERS) else rest
    rest = text.removeprefix(NPM_EXACT_PIN).strip()
    return rest if NPM_EXACT_VERSION.match(rest) else ""


def base_purl(name: str, ecosystem: str) -> str:
    """Return the purl for a package with no version attached."""
    return f"pkg:{ecosystem}/{purl_name(name, ecosystem)}"


def purl_name(name: str, ecosystem: str) -> str:
    """Return the name as a PURL spells it, percent-encoding an npm scope's `@`."""
    check_ecosystem(ecosystem)
    if ecosystem == NPM and name.startswith(NPM_SCOPE_PREFIX):
        return NPM_SCOPE_ENCODED + name[len(NPM_SCOPE_PREFIX):]
    return name
