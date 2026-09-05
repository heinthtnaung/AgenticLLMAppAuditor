"""Whether a path the generator reported names a lockfile, by its basename.

Split from test_package_names.py, which owns the naming and version rules: this
is the one question in that module about a *file* rather than a package. The
answer decides `locked`, and `locked` decides whether a version reaches a purl,
so a wrong yes here puts a guessed version into the key advisories join on.

Equality with "/yarn.lock" would be the obvious implementation and is wrong
twice over: the generator writes scan-root-relative paths with a leading slash,
and a monorepo's workspace lockfile sits several directories down.
"""

import pytest

from deps.package_names import (
    LOCKFILE_NAMES,
    NPM_LOCKFILES,
    PYPI_LOCKFILES,
    is_lockfile_path,
)

# The four paths the fix was written against, and what each must answer.
ROOT_LOCKFILE = "/yarn.lock"
NESTED_LOCKFILE = "/packages/a/yarn.lock"
MANIFEST = "/package.json"
PYPI_MANIFEST_PATH = "/requirements.txt"

# A file whose name merely ends in a lockfile's name. Basename matching splits
# on the separator, so this is a different file and must not count.
LOOKALIKE = "/vendor/notyarn.lock"


def test_a_lockfile_at_the_scan_root_is_one() -> None:
    """The plain case: Syft writes the repository's own yarn.lock as /yarn.lock."""
    assert is_lockfile_path(ROOT_LOCKFILE) is True


def test_a_lockfile_in_a_workspace_directory_is_one_too() -> None:
    """A monorepo pins per package, so the path is not equal to the bare name."""
    assert is_lockfile_path(NESTED_LOCKFILE) is True


def test_a_manifest_is_not_a_lockfile() -> None:
    """package.json declares ranges; a version read from it is a guess, not a pin.

    This is the case the document-wide flag got wrong, and the reason `locked`
    has to be decided per component rather than per directory.
    """
    assert is_lockfile_path(MANIFEST) is False


def test_a_requirements_file_is_not_a_lockfile() -> None:
    """The same on the Python side: requirements.txt is a declaration, not a resolution."""
    assert is_lockfile_path(PYPI_MANIFEST_PATH) is False


def test_the_empty_string_is_not_a_lockfile() -> None:
    """A property with no value must answer no rather than raise or match by accident."""
    assert is_lockfile_path("") is False


def test_a_name_merely_ending_in_a_lockfile_name_is_not_one() -> None:
    """notyarn.lock is a different file, so the match is on the whole basename."""
    assert is_lockfile_path(LOOKALIKE) is False


@pytest.mark.parametrize("lockfile", sorted(LOCKFILE_NAMES))
def test_every_listed_lockfile_is_recognised_at_the_root(lockfile: str) -> None:
    """Both ecosystems' lockfiles count, since `locked` is never keyed on the ecosystem."""
    assert is_lockfile_path(f"/{lockfile}") is True


@pytest.mark.parametrize("lockfile", sorted(LOCKFILE_NAMES))
def test_every_listed_lockfile_is_recognised_nested(lockfile: str) -> None:
    """The basename rule applies to all five, not only to the one it was written for."""
    assert is_lockfile_path(f"/packages/a/{lockfile}") is True


def test_the_parametrised_lists_really_cover_both_ecosystems() -> None:
    """Guards the two above: a check running over an empty set would pass silently."""
    assert len(LOCKFILE_NAMES) == len(PYPI_LOCKFILES) + len(NPM_LOCKFILES) == 5
