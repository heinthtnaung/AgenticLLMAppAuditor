"""Guards on finding the manifests a scan read no version from, and on what counts as read."""

import os
from pathlib import Path
from typing import Iterator

import pytest

from deps.manifests import LOCKS_BY_MANIFEST, ManifestsUnreadable, unread_manifests

# What Syft 1.52 was measured reading: each manifest alone gave no package, and
# beside each of these locks gave the locked one. `test_manifests_live.py`
# measures it again against the Syft on this machine.
MEASURED = {
    "package.json": {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"},
    "composer.json": {"composer.lock"},
    "Gemfile": {"Gemfile.lock"},
}
MEASURED_PAIRS = [
    ("package.json", "package-lock.json"),
    ("package.json", "yarn.lock"),
    ("package.json", "pnpm-lock.yaml"),
    ("composer.json", "composer.lock"),
    ("Gemfile", "Gemfile.lock"),
]
UNLISTABLE = 0o000
OWNER_ALL = 0o700
NEEDS_PERMISSIONS = pytest.mark.skipif(
    os.geteuid() == 0, reason="root lists anything, so no unreadable directory can be made"
)


def written(root: Path, *paths: str) -> Path:
    """Lay out empty files at these paths within `root`, and give `root`."""
    for relative in paths:
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text("", encoding="utf-8")
    return root


@pytest.fixture
def locked_out(tmp_path: Path) -> Iterator[Path]:
    """Give a repository with one directory nobody can list, and unlock it after."""
    closed = written(tmp_path, "shut/package.json") / "shut"
    closed.chmod(UNLISTABLE)
    yield tmp_path
    closed.chmod(OWNER_ALL)


def test_the_table_names_exactly_the_locks_recorded_as_measured():
    assert {one: set(locks) for one, locks in LOCKS_BY_MANIFEST.items()} == MEASURED


@pytest.mark.parametrize("manifest", sorted(MEASURED))
def test_a_manifest_with_no_lock_file_beside_it_is_named(tmp_path, manifest):
    assert unread_manifests(written(tmp_path, manifest)) == (manifest,)


@pytest.mark.parametrize("manifest, lock", MEASURED_PAIRS)
def test_a_manifest_beside_a_lock_file_syft_reads_is_not_named(tmp_path, manifest, lock):
    assert unread_manifests(written(tmp_path, manifest, lock)) == ()


def test_each_is_named_by_its_path_within_the_repository_in_sorted_order(tmp_path):
    repository = written(tmp_path, "frontend/package.json", "package.json", "api/Gemfile")
    assert unread_manifests(repository) == ("api/Gemfile", "frontend/package.json", "package.json")


def test_another_ecosystems_lock_file_does_not_cover_a_manifest(tmp_path):
    assert unread_manifests(written(tmp_path, "package.json", "composer.lock")) == ("package.json",)


def test_an_installed_node_modules_tree_is_not_read_so_the_manifest_is_named(tmp_path):
    # Measured: in a `dir:` scan Syft reads no `node_modules/*/package.json`.
    repository = written(tmp_path, "package.json", "node_modules/lodash/package.json")
    assert unread_manifests(repository) == ("package.json",)


def test_a_shrinkwrap_file_is_not_read_so_the_manifest_is_named(tmp_path):
    # Measured: Syft 1.52 reads no `npm-shrinkwrap.json`, in either lockfile format.
    repository = written(tmp_path, "package.json", "npm-shrinkwrap.json")
    assert unread_manifests(repository) == ("package.json",)


def test_the_history_is_not_walked(tmp_path):
    assert unread_manifests(written(tmp_path, ".git/package.json")) == ()


def test_composers_installed_tree_is_not_walked(tmp_path):
    installed = ["vendor/monolog/monolog/composer.json", "vendor/psr/log/composer.json"]
    assert unread_manifests(written(tmp_path, "composer.json", "composer.lock", *installed)) == ()


def test_bundlers_installed_tree_is_not_walked(tmp_path):
    installed = "vendor/bundle/ruby/3.1.0/gems/rails-6.0.0/Gemfile"
    assert unread_manifests(written(tmp_path, "Gemfile", "Gemfile.lock", installed)) == ()


def test_a_manifest_under_vendor_is_not_named_even_with_no_lock_anywhere(tmp_path):
    # Accepted: `vendor/` is skipped whole, so a manifest there is taken to be
    # a dependency's own, and one that is not goes unnamed.
    assert unread_manifests(written(tmp_path, "vendor/library/composer.json")) == ()


def test_a_projects_own_manifest_under_a_nested_vendor_is_not_named_either(tmp_path):
    # Accepted cost: a directory named `vendor` is skipped at any depth, so the
    # project's own manifest there goes unnamed. Narrowing the skip turns this red.
    own = "app/vendor/own/package.json"
    assert unread_manifests(written(tmp_path, "package.json", "package-lock.json", own)) == ()


@pytest.mark.parametrize("manifest", ["Cargo.toml", "pyproject.toml"])
def test_a_manifest_outside_the_table_is_not_named_although_syft_reads_nothing_from_it(
    tmp_path, manifest
):
    # Accepted: both were measured yielding no package without a lock, and are
    # left out of the table on purpose, so a repository of either still reads clean.
    assert unread_manifests(written(tmp_path, manifest)) == ()


def test_a_workspace_member_is_named_although_syft_reads_it_from_the_root_lock(tmp_path):
    # Accepted: only the manifest's own directory is looked in, and Syft was
    # measured reading an npm workspace member's packages from the root's lock.
    repository = written(tmp_path, "package.json", "package-lock.json", "packages/a/package.json")
    assert unread_manifests(repository) == ("packages/a/package.json",)


@NEEDS_PERMISSIONS
def test_a_directory_that_cannot_be_listed_stops_the_walk_and_says_what_it_was_doing(locked_out):
    said = "cannot list .*shut to look for manifests: Permission denied"
    with pytest.raises(ManifestsUnreadable, match=said):
        unread_manifests(locked_out)


def test_a_repository_that_is_not_there_stops_the_walk(tmp_path):
    said = "cannot list .*absent to look for manifests: No such file or directory"
    with pytest.raises(ManifestsUnreadable, match=said):
        unread_manifests(tmp_path / "absent")
