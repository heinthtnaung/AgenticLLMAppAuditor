"""Exactly one module under `src/` imports the cloud client, and an audit loads none of it.

`tests/parsing/test_offline_containment.py` widened `NETWORK_MODULES` to two
when `cloud_client.py` moved into `src/`, which says a second module *can*
reach the internet. What makes that acceptable is narrower and is asserted
here: only `compare_run.py` imports it, `main.py` imports `compare_run` from
inside the `--compare-models` branch, and nothing in the import graph a default
audit loads reaches either. `tests/cli/test_main_offline.py` holds the runtime
complement -- a real audit, with `sys.modules` checked afterwards -- which
catches a *deferred* import on the audit path that this file cannot see, while
this file catches a module-scope one that a shared pytest process cannot.

`experiments/compare_models.py` imports `cloud_client` too. That is outside
`src/`, is not part of the tool, and `tests/test_experiments_containment.py`
already asserts nothing under `src/` can reach it, so the sweep below is scoped
to `src/` and says so rather than pretending the study does not exist.

Nothing here runs anything: the question is "could it?", which a run cannot
answer, because a branch not taken looks exactly like a branch that is absent.
"""

import ast
from pathlib import Path

from ast_scan import imported_modules, module_name, modules_importing, parse, source_files
from conftest import REPO_ROOT, SRC_DIR

CLOUD_CLIENT = "cloud_client"
COMPARE_RUN = "compare_run"

# The one module in `src/` allowed to name it. Exact, so a second importer
# cannot appear without this failing.
CLOUD_CLIENT_IMPORTERS = frozenset({f"{COMPARE_RUN}.py"})

# The command line. It must reach the comparison somewhere -- otherwise the
# flag does nothing -- but never at module scope, or importing `main` would
# import the cloud client with it.
MAIN_MODULE = SRC_DIR / "main.py"
FLAG_ONLY_MODULES = frozenset({f"{CLOUD_CLIENT}.py", f"{COMPARE_RUN}.py"})

# Three modules a default audit certainly loads, so "the graph was walked" is
# asserted rather than assumed: an empty graph would pass every sweep below.
AUDIT_GRAPH_FLOOR = frozenset({"audit_run.py", "outputs.py", "checks/run_checks.py"})

# The study's own copy, outside `src/` and outside this sweep.
STUDY_MODULE = REPO_ROOT / "experiments" / "compare_models.py"

# A second importer, planted in a fake tree, to prove the search still fires.
PLANTED_FILE = "planted.py"
PLANTED_IMPORT = "import cloud_client\n"


def module_scope_import_names(path: Path) -> set[str]:
    """Every module a file imports at module scope; `from x import y` counts as both names.

    Both spellings, because `from checks import advise` names the package in
    the syntax tree and the submodule in the filesystem, and the walk below has
    to follow the file.
    """
    tree = parse(path)
    plain = {alias.name for node in tree.body if isinstance(node, ast.Import)
             for alias in node.names}
    partial = {node.module for node in tree.body
               if isinstance(node, ast.ImportFrom) and node.module}
    return plain | partial | {f"{node.module}.{alias.name}" for node in tree.body
                              if isinstance(node, ast.ImportFrom) and node.module
                              for alias in node.names}


def source_path(import_name: str) -> Path | None:
    """The file under `src/` a dotted import names, or None when it names something else."""
    candidate = SRC_DIR / (import_name.replace(".", "/") + ".py")
    return candidate if candidate.is_file() else None


def imported_source_files(path: Path) -> list[Path]:
    """The files under `src/` that one module's module-scope imports resolve to."""
    found = [source_path(name) for name in module_scope_import_names(path)]
    return [resolved for resolved in found if resolved is not None]


def modules_loaded_by(start: Path) -> set[str]:
    """Every module under `src/` that importing one module pulls in, transitively."""
    seen, queue = {module_name(start)}, [start]
    while queue:
        fresh = [path for path in imported_source_files(queue.pop())
                 if module_name(path) not in seen]
        seen |= {module_name(path) for path in fresh}
        queue += fresh
    return seen


# --- who imports it -----------------------------------------------------------

def test_only_the_comparison_module_imports_the_cloud_client() -> None:
    """The containment `cloud_client.py`'s own docstring claims, asserted over all of `src/`."""
    assert modules_importing(CLOUD_CLIENT) == set(CLOUD_CLIENT_IMPORTERS)


def test_the_module_named_as_the_only_importer_is_a_module_that_exists() -> None:
    """Guard: a renamed file would make the set above agree by naming nothing real."""
    assert {module_name(path) for path in source_files()} >= CLOUD_CLIENT_IMPORTERS


def test_that_the_sweep_would_notice_a_second_importer(tmp_path) -> None:
    """Mutation check: plant a module that imports the client and see the search name it."""
    (tmp_path / PLANTED_FILE).write_text(PLANTED_IMPORT, encoding="utf-8")
    assert modules_importing(CLOUD_CLIENT, tmp_path) == {PLANTED_FILE}


# --- what an audit loads ------------------------------------------------------

def test_the_command_line_names_neither_module_at_import_time() -> None:
    """Importing `main` must not import a socket: the flag's branch is the boundary."""
    named = {f"{name}.py" for name in module_scope_import_names(MAIN_MODULE)}
    assert named & FLAG_ONLY_MODULES == set()


def test_nothing_a_default_audit_loads_imports_the_cloud_client() -> None:
    """The reachability claim: no module in `main`'s import graph names the client."""
    assert modules_importing(CLOUD_CLIENT) & modules_loaded_by(MAIN_MODULE) == set()


def test_neither_flagged_module_is_in_the_graph_at_all() -> None:
    """`compare_run.py` is loaded by the flag, not by importing the command line."""
    assert modules_loaded_by(MAIN_MODULE) & FLAG_ONLY_MODULES == set()


def test_the_graph_walked_is_the_audits_own() -> None:
    """Guard: a walk that resolved nothing would satisfy both sweeps above."""
    assert modules_loaded_by(MAIN_MODULE) >= AUDIT_GRAPH_FLOOR


def test_the_command_line_does_reach_the_comparison_somewhere() -> None:
    """Guard: a `main.py` that dropped the flag entirely would pass the tests above."""
    assert COMPARE_RUN in imported_modules(parse(MAIN_MODULE))


def test_the_study_keeps_its_own_importer_outside_the_source_tree() -> None:
    """The one other importer in the repository, named so the sweep's scope is honest."""
    assert CLOUD_CLIENT in imported_modules(parse(STUDY_MODULE))
    assert SRC_DIR not in STUDY_MODULE.parents
