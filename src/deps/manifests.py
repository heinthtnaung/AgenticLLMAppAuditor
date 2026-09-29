"""The manifests in a repository that the scan could read no installed version from.

**A manifest with no lock file is not a clean result.** Scanning a directory,
Syft reads installed versions from lock files and from nothing else, so a
`package.json` alone yields no package at all, and every dependency it declares
goes unchecked. A report of "0 findings" over it reads exactly like a repository
with nothing wrong, which is the one thing a report must never look like by
accident. So each such manifest is found and named.

**The table is what was measured, not what seemed likely.** Every entry was run
through Syft 1.52 twice, alone and beside each lock file listed: alone it
yielded no package, beside the lock it yielded the locked one. The same runs
showed what does *not* count. Syft reads neither `node_modules/` nor
`npm-shrinkwrap.json` in a directory scan, so a manifest beside only those is
still named. A manifest outside the table is not named at all, whatever it
declares.
"""

import os
from itertools import chain
from pathlib import Path
from typing import Iterator

# Each manifest, and the lock files Syft 1.52 reads its versions from.
LOCKS_BY_MANIFEST = {
    "package.json": ("package-lock.json", "yarn.lock", "pnpm-lock.yaml"),
    "composer.json": ("composer.lock",),
    "Gemfile": ("Gemfile.lock",),
}
# Never walked: the history, and the installed trees a lock file describes --
# npm's, and the one Composer and Bundler both put under `vendor/`. A manifest
# in there is a dependency's own, and Syft reads its version from the lock.
SKIPPED_DIRECTORIES = frozenset({".git", "node_modules", "vendor"})


class ManifestsUnreadable(RuntimeError):
    """A directory the walk could not list, so any manifest in it would go unnamed."""


def unread_manifests(repository: Path) -> tuple[str, ...]:
    """Name every manifest with no lock file beside it, by its path within the repository."""
    found = [unread_in(repository, directory, names) for directory, names in walked(repository)]
    return tuple(sorted(chain.from_iterable(found)))


def unread_in(repository: Path, directory: Path, names: set[str]) -> list[str]:
    """Name one directory's unread manifests by their paths within the repository."""
    return [relative_path(repository, directory, one) for one in unread_among(names)]


def unread_among(names: set[str]) -> list[str]:
    """Name the manifests among one directory's files that no lock file beside them covers."""
    return [
        manifest
        for manifest, locks in LOCKS_BY_MANIFEST.items()
        if manifest in names and names.isdisjoint(locks)
    ]


def walked(repository: Path) -> Iterator[tuple[Path, set[str]]]:
    """Give each directory the scan reads with its file names, passing over none silently."""
    for directory, subdirectories, files in os.walk(repository, onerror=refuse_unreadable):
        # Pruned in place, which is how `os.walk` is told not to descend.
        subdirectories[:] = sorted(set(subdirectories) - SKIPPED_DIRECTORIES)
        yield Path(directory), set(files)


def refuse_unreadable(fault: OSError) -> None:
    """Stop at a directory that cannot be listed, rather than pass over its manifests."""
    said = f"cannot list {fault.filename} to look for manifests: {fault.strerror}"
    raise ManifestsUnreadable(said) from fault


def relative_path(repository: Path, directory: Path, manifest: str) -> str:
    """Give one manifest's path within the repository, the same on every machine."""
    return (directory.relative_to(repository) / manifest).as_posix()
