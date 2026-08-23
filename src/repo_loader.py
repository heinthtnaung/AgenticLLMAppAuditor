"""Walks an audited repository and returns the source files worth analysing."""

from collections.abc import Iterator
from pathlib import Path

from languages import IGNORED_SUFFIXES, SOURCE_EXTENSIONS

# Directories that never contain the audited app's own source code.
SKIP_DIRS = frozenset({
    ".git",
    # Python
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "site-packages",
    # JavaScript and TypeScript
    "node_modules",
    "dist",
    "build",
    "out",
    ".next",
    ".turbo",
    "coverage",
})

# Files above this size are generated or vendored, not hand-written app code.
MAX_FILE_BYTES = 1_000_000


def _check_repo_root(repo_path: str) -> Path:
    """Return the repository root, failing loudly if it is not a usable directory."""
    root = Path(repo_path)
    if not root.exists():
        raise FileNotFoundError(f"repository path does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"repository path is not a directory: {root}")
    return root


def _walk_source_files(root: Path) -> Iterator[Path]:
    """Yield every readable source file under root that is not in a skipped directory."""
    for extension in SOURCE_EXTENSIONS:
        for candidate in root.rglob(f"*{extension}"):
            if candidate.is_symlink():
                # A downloaded repository is untrusted: a symlink can point at
                # anything on this machine, and its contents would end up in
                # the report.
                continue
            if not candidate.is_file() or candidate.name.endswith(IGNORED_SUFFIXES):
                continue
            if any(part in SKIP_DIRS for part in candidate.relative_to(root).parts):
                continue
            yield candidate


def list_source_files(repo_path: str) -> list[Path]:
    """Return the repository's source files, skipping skip-dirs and oversized files."""
    root = _check_repo_root(repo_path)
    kept = [f for f in _walk_source_files(root) if f.stat().st_size <= MAX_FILE_BYTES]
    return sorted(set(kept))


def list_oversized_files(repo_path: str) -> list[Path]:
    """Return the source files skipped for size, so the caller can report them."""
    root = _check_repo_root(repo_path)
    skipped = [f for f in _walk_source_files(root) if f.stat().st_size > MAX_FILE_BYTES]
    return sorted(set(skipped))
