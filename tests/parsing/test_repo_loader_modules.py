"""The top-level names an import could resolve to inside the audited repository.

This is the list that tells the app's own modules apart from packages it forgot
to declare. Too small and the app's own code is reported as a missing
dependency; too large and a genuine missing dependency is hidden.
"""

import pytest
from conftest import CORPUS_DIR, require_corpus
from parsing.repo_loader import local_module_names

SUPPORT_AGENT = "vuln-app-1-support-agent"

# corpus/vuln-app-1-support-agent ships exactly these four modules.
SUPPORT_AGENT_MODULES = frozenset({"main", "tools", "transaction_db", "utils"})


def test_a_top_level_module_contributes_its_own_name(tmp_path) -> None:
    """`main.py` at the root is importable as `main`, so `main` is a local name."""
    (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
    assert local_module_names(str(tmp_path)) == frozenset({"main"})


def test_a_nested_module_contributes_its_package_name(tmp_path) -> None:
    """`pkg/mod.py` is imported as `pkg.mod`, so the local name is `pkg`, not `mod`."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    assert local_module_names(str(tmp_path)) == frozenset({"pkg"})


def test_the_extension_is_dropped_from_a_top_level_name(tmp_path) -> None:
    """A name is what an import statement writes, so it never carries `.py` or `.ts`."""
    (tmp_path / "agent.ts").write_text("const x = 1;\n", encoding="utf-8")
    assert local_module_names(str(tmp_path)) == frozenset({"agent"})


def test_an_empty_repository_has_no_local_modules(tmp_path) -> None:
    """No source files means no local names, which is an answer rather than an error."""
    assert local_module_names(str(tmp_path)) == frozenset()


def test_installed_packages_are_not_local_modules(tmp_path) -> None:
    """node_modules holds other people's code, so it must not shadow a real finding."""
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "express.js").write_text("const x = 1;\n", encoding="utf-8")
    assert local_module_names(str(tmp_path)) == frozenset({"app"})


def test_the_corpus_app_reports_exactly_its_four_modules() -> None:
    """The real fixture yields main, tools, transaction_db and utils, and nothing else."""
    require_corpus(SUPPORT_AGENT)
    assert local_module_names(str(CORPUS_DIR / SUPPORT_AGENT)) == SUPPORT_AGENT_MODULES


def test_a_missing_repository_path_fails_loudly(tmp_path) -> None:
    """A path that does not exist is named in the error, not silently empty."""
    missing = tmp_path / "no-such-repo"
    with pytest.raises(FileNotFoundError) as error:
        local_module_names(str(missing))
    assert str(missing) in str(error.value)


def test_a_file_instead_of_a_repository_is_rejected(tmp_path) -> None:
    """A single file is not a repository, and saying so beats returning nothing."""
    target = tmp_path / "main.py"
    target.write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        local_module_names(str(target))
