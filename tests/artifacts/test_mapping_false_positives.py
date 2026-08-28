"""Supply-chain findings the mapping used to invent out of nothing.

Every case here was once reported as "a package this app uses and never
declared". None of them is a package at all: they are the app's own modules,
the Node runtime, and a TypeScript path alias. A false finding costs a reader
the trust the real ones need.
"""

from artifacts.mapping import FIRST_PARTY, STDLIB, USED_BUT_UNDECLARED, build_mapping
from artifacts.surface import DATA_SOURCE, TOOL_CALL, Surface
from dependency_fixtures import corpus_sbom
from parsing.languages import PYTHON, TYPESCRIPT

# The corpus app's own modules, as the repo loader reports them.
CORPUS_LOCAL_MODULES = frozenset({"main", "tools", "transaction_db", "utils"})


def python_surface(module: str) -> Surface:
    """A Python surface importing the given module."""
    return Surface(TOOL_CALL, "GetCurrentUser", "main.py", 10, PYTHON, "", module)


def typescript_surface(module: str) -> Surface:
    """A TypeScript surface importing the given module."""
    return Surface(DATA_SOURCE, "readFile", "src/agent.ts", 4, TYPESCRIPT, "", module)


def reason_for(surface: Surface, local: frozenset = frozenset()) -> str:
    """Map one surface and return the single outcome it was given."""
    return build_mapping([surface], corpus_sbom(), local)["entries"][0]["reason"]


def test_the_apps_own_module_is_first_party() -> None:
    """`from tools import ...` is the app's own file, not a package it forgot."""
    assert reason_for(python_surface("tools"), CORPUS_LOCAL_MODULES) == FIRST_PARTY


def test_the_same_import_without_local_modules_reads_as_undeclared() -> None:
    """Without the local module list the same import becomes a false finding.

    This is the false positive itself: it shows `local_modules` is what
    prevents it, rather than something incidental.
    """
    assert reason_for(python_surface("tools")) == USED_BUT_UNDECLARED


def test_a_submodule_of_the_apps_own_package_is_first_party() -> None:
    """`utils.loaders` belongs to the app's `utils`, so the top-level name decides it."""
    assert reason_for(python_surface("utils.loaders"), CORPUS_LOCAL_MODULES) == FIRST_PARTY


def test_a_local_module_shadowing_the_stdlib_is_first_party() -> None:
    """A local `tokenize.py` is what `import tokenize` gets, so the app's file wins."""
    assert reason_for(python_surface("tokenize"), frozenset({"tokenize"})) == FIRST_PARTY


def test_the_node_fs_builtin_is_stdlib() -> None:
    """`fs` ships with Node, so no npm package could be missing for it."""
    assert reason_for(typescript_surface("fs")) == STDLIB


def test_the_node_path_builtin_is_stdlib() -> None:
    """`path` is a Node builtin, and asking Python's stdlib list called it undeclared."""
    assert reason_for(typescript_surface("path")) == STDLIB


def test_the_explicit_node_prefix_is_stdlib() -> None:
    """`node:fs/promises` is the same builtin written the explicit way."""
    assert reason_for(typescript_surface("node:fs/promises")) == STDLIB


def test_a_typescript_path_alias_is_first_party() -> None:
    """`@/lib/loaders` is a tsconfig alias for the app's own code; no package is named that."""
    assert reason_for(typescript_surface("@/lib/loaders")) == FIRST_PARTY


def test_a_real_npm_package_is_still_reported_as_undeclared() -> None:
    """express is a genuine dependency, so the fixes above must not silence it."""
    assert reason_for(typescript_surface("express")) == USED_BUT_UNDECLARED


def test_a_scoped_npm_package_is_still_reported_as_undeclared() -> None:
    """`@langchain/langgraph` starts with `@` but is a package, not a path alias."""
    surface = typescript_surface("@langchain/langgraph/prebuilt")
    assert reason_for(surface) == USED_BUT_UNDECLARED


def test_a_real_undeclared_python_package_is_still_reported() -> None:
    """`import yaml` is PyYAML and undeclared, which is the finding the rest must not hide."""
    assert reason_for(python_surface("yaml"), CORPUS_LOCAL_MODULES) == USED_BUT_UNDECLARED
