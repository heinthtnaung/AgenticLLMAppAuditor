"""The repo loader must return exactly the audited app's own Python files."""

import pytest
from conftest import CORPUS_DIR
from repo_loader import MAX_FILE_BYTES, SKIP_DIRS, list_oversized_files, list_python_files

SUPPORT_AGENT = CORPUS_DIR / "vuln-app-1-support-agent"

# The demo app's own modules, as committed under corpus/.
SUPPORT_AGENT_FILES = ["main.py", "tools.py", "transaction_db.py", "utils.py"]


def test_lists_exactly_the_support_agent_files() -> None:
    """Demo app 1 yields its four modules and nothing else."""
    found = list_python_files(str(SUPPORT_AGENT))
    assert [path.name for path in found] == SUPPORT_AGENT_FILES


def test_returned_paths_exist_and_are_python() -> None:
    """Every returned path is a real .py file on disk."""
    for path in list_python_files(str(SUPPORT_AGENT)):
        assert path.is_file() and path.suffix == ".py"


def test_skips_files_inside_skip_dirs(tmp_path) -> None:
    """Nothing inside a skip-dir is analysed, only the app's own code."""
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    for skipped in SKIP_DIRS:
        (tmp_path / skipped).mkdir()
        (tmp_path / skipped / "vendored.py").write_text("x = 2\n", encoding="utf-8")
    found = list_python_files(str(tmp_path))
    assert [path.name for path in found] == ["app.py"]


def test_skips_nested_venv_and_pycache(tmp_path) -> None:
    """A skip-dir nested below the repo root is skipped too."""
    nested = tmp_path / "pkg" / ".venv" / "lib"
    nested.mkdir(parents=True)
    (nested / "dep.py").write_text("x = 1\n", encoding="utf-8")
    cache = tmp_path / "pkg" / "__pycache__"
    cache.mkdir()
    (cache / "app.cpython-311.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "pkg" / "app.py").write_text("x = 1\n", encoding="utf-8")
    assert [path.name for path in list_python_files(str(tmp_path))] == ["app.py"]


def test_oversized_file_is_excluded(tmp_path) -> None:
    """A file above MAX_FILE_BYTES is left out of the analysed list."""
    (tmp_path / "small.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "generated.py").write_text("# " + "a" * MAX_FILE_BYTES, encoding="utf-8")
    assert [path.name for path in list_python_files(str(tmp_path))] == ["small.py"]


def test_oversized_file_is_reported(tmp_path) -> None:
    """The oversized file is reported so it is never dropped silently."""
    (tmp_path / "small.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "generated.py").write_text("# " + "a" * MAX_FILE_BYTES, encoding="utf-8")
    assert [path.name for path in list_oversized_files(str(tmp_path))] == ["generated.py"]


def test_repo_without_python_files_returns_empty(tmp_path) -> None:
    """A valid directory holding no Python returns an empty list, not an error."""
    (tmp_path / "README.md").write_text("docs only\n", encoding="utf-8")
    assert list_python_files(str(tmp_path)) == []


def test_missing_repo_path_raises_file_not_found(tmp_path) -> None:
    """A path that does not exist fails loudly with the path in the message."""
    missing = tmp_path / "nope"
    with pytest.raises(FileNotFoundError, match="nope"):
        list_python_files(str(missing))


def test_file_instead_of_directory_raises_not_a_directory(tmp_path) -> None:
    """Pointing the loader at a file fails loudly instead of guessing."""
    target = tmp_path / "app.py"
    target.write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(NotADirectoryError, match="app.py"):
        list_python_files(str(target))
