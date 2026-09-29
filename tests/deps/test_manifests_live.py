"""The Syft measurements `deps.manifests` rests on, taken again, and skipped unless asked for.

`LOCKS_BY_MANIFEST` says which lock files Syft reads a manifest's versions from,
and every other test takes the table's word for it. This one does not: it lays
each case out in `tmp_path` and runs Syft the way the audit does, so a Syft that
starts or stops reading a file turns this red instead of leaving the table wrong:

    SYFT_LIVE_SCAN=1 python -m pytest tests/deps/test_manifests_live.py

It is off by default because the ordinary suite may not depend on Syft being
installed, and where Syft is absent it skips with the reason.
"""

import os
from itertools import chain
from pathlib import Path

import pytest

from deps import syft_runner
from deps.manifests import LOCKS_BY_MANIFEST
from lock_samples import (
    INSTALLED_LODASH,
    LEFT_OUT,
    LOCKED_PACKAGE,
    LOCKS,
    MANIFESTS,
    PACKAGE_JSON,
    PACKAGE_LOCK,
    WORKSPACE,
)

LIVE = "SYFT_LIVE_SCAN"

pytestmark = pytest.mark.skipif(
    not os.environ.get(LIVE), reason=f"set {LIVE}=1 to run Syft over each case for real"
)


def pairs_of(manifest: str, locks: tuple[str, ...]) -> list[tuple[str, str]]:
    """Pair one manifest with each lock file the table says Syft reads it from."""
    return [(manifest, lock) for lock in locks]


# Built below `pairs_of`, which it needs, from the table itself rather than a copy of it.
TABLE_PAIRS = list(chain.from_iterable(pairs_of(*entry) for entry in LOCKS_BY_MANIFEST.items()))


@pytest.fixture(autouse=True)
def syft_installed() -> None:
    """Skip where Syft is not on this machine, which says nothing about the table."""
    if not syft_runner.is_available():
        pytest.skip("syft is not installed on this machine")


def packages_read(root: Path, files: dict[str, str]) -> tuple[str, ...]:
    """Lay one case out and name every package the audit's own Syft run reads from it."""
    for relative, content in files.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(content, encoding="utf-8")
    catalogue = syft_runner.scan_directory(root)
    return tuple(one.name for one in (*catalogue.components, *catalogue.unidentified))


@pytest.mark.parametrize("manifest", sorted(LOCKS_BY_MANIFEST))
def test_each_manifest_in_the_table_alone_yields_no_package(tmp_path, manifest):
    assert packages_read(tmp_path, {manifest: MANIFESTS[manifest]}) == ()


@pytest.mark.parametrize("manifest, lock", TABLE_PAIRS)
def test_each_manifest_beside_each_lock_in_the_table_yields_the_locked_package(
    tmp_path, manifest, lock
):
    read = packages_read(tmp_path, {manifest: MANIFESTS[manifest], lock: LOCKS[lock]})
    assert LOCKED_PACKAGE[manifest] in read


def test_a_shrinkwrap_file_is_not_read_although_the_same_bytes_as_a_package_lock_are(tmp_path):
    shrinkwrapped = {"package.json": PACKAGE_JSON, "npm-shrinkwrap.json": PACKAGE_LOCK}
    assert packages_read(tmp_path, shrinkwrapped) == ()


def test_an_installed_node_modules_tree_is_not_read(tmp_path):
    installed = {"package.json": PACKAGE_JSON, "node_modules/lodash/package.json": INSTALLED_LODASH}
    assert packages_read(tmp_path, installed) == ()


@pytest.mark.parametrize("manifest", sorted(LEFT_OUT))
def test_a_manifest_left_out_of_the_table_yields_no_package_alone_either(tmp_path, manifest):
    assert packages_read(tmp_path, {manifest: LEFT_OUT[manifest]}) == ()


def test_a_workspace_members_dependency_is_read_from_the_root_lock(tmp_path):
    # Which is why `test_manifests.py` pins naming the member as a false report.
    assert "lodash" in packages_read(tmp_path, WORKSPACE)
