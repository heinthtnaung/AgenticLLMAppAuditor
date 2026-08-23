"""Walks an audited repository and returns the Python files worth analysing."""

from collections.abc import Iterator
from pathlib import Path

# Directories that never contain the audited app's own source code.
SKIP_DIRS = frozenset({
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    "site-packages",
})

# Files above this size are generated or vendored, not hand-written app code.
MAX_FILE_BYTES = 1_000_000

PYTHON_GLOB = "*.py"


def _check_repo_root(repo_path: str) -> Path:
    """Return the repository root, failing loudly if it is not a usable directory."""
    root = Path(repo_path)
    if not root.exists():
        raise FileNotFoundError(f"repository path does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"repository path is not a directory: {root}")
    return root


def _walk_python_files(root: Path) -> Iterator[Path]:
    """Yield every Python file under root that is not inside a skipped directory."""
    for candidate in root.rglob(PYTHON_GLOB):
        if not candidate.is_file():
            continue
        if any(part in SKIP_DIRS for part in candidate.relative_to(root).parts):
            continue
        yield candidate


def list_python_files(repo_path: str) -> list[Path]:
    """Return the repository's Python files, skipping skip-dirs and oversized files."""
    root = _check_repo_root(repo_path)
    kept = [f for f in _walk_python_files(root) if f.stat().st_size <= MAX_FILE_BYTES]
    return sorted(kept)


def list_oversized_files(repo_path: str) -> list[Path]:
    """Return the Python files skipped for size, so the caller can report them."""
    root = _check_repo_root(repo_path)
    skipped = [f for f in _walk_python_files(root) if f.stat().st_size > MAX_FILE_BYTES]
    return sorted(skipped)
