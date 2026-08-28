"""No module under src/ writes a command that commits, merges, installs or executes.

"It never commits" is a negative, and running the tool cannot prove one: a code
path that was not taken looks identical to one that does not exist. So it is
asserted over the source instead. One module is allowed to start a process --
`deps/syft_runner.py`, which runs Syft to build the bill of materials -- and the
test names it rather than exempting subprocess use in general.

Limit: the two command checks match substrings of string *literals*, so a command
assembled at runtime -- `f"git {verb}"`, or a program name read from config --
is not seen. The process, import and call checks are structural and have no such
gap: they match the call itself, whatever its arguments say.

The behavioural half, that a real audit leaves `corpus/` byte-identical, is in
test_no_mutation.py.
"""

import ast
from pathlib import Path

from conftest import SRC_DIR
from deps.syft_runner import GENERATOR_NAME

# Calls that start another program. `subprocess.SubprocessError` in main.py is
# an attribute of the module, not a call on it, so it does not match.
PROCESS_LAUNCHERS = frozenset({
    "subprocess.run", "subprocess.Popen", "subprocess.call",
    "subprocess.check_call", "subprocess.check_output",
    "os.system", "os.popen", "os.execv", "os.execvp", "os.spawnv", "os.spawnvp",
})

# The single module allowed to start one, and the single program it may start.
GENERATOR_MODULE = "deps/syft_runner.py"

# The exemption is by module, not by command: the process test asserts set
# equality with GENERATOR_MODULE, so no other module may start a process at all,
# and `git checkout` is banned outright below. Task 3.8a needs both -- it runs
# `git rev-parse` to check a fixture's pin and `git checkout` to restore it --
# so it must add its own named module here, deliberately, rather than discover
# the collision.
MUTATING_COMMANDS = (
    "git commit", "git push", "git merge", "git apply", "git am",
    "git checkout", "git reset", "git rebase", "gh pr", "pull request",
)

# Fetching the audited app's dependencies, or starting the app itself. Phase 3
# reads the corpus; it does not run it, and it does not install into .venv.
EXECUTION_COMMANDS = (
    "pip install", "npm install", "npm ci", "yarn install", "poetry install",
    "streamlit run", "uvicorn", "npm run",
)

# Ways to run the audited app's code inside this process rather than beside it.
EXECUTION_IMPORTS = frozenset({"runpy", "imp", "importlib", "importlib.util"})
EXECUTION_CALLS = frozenset({"exec", "eval", "__import__", "compile"})

# Violations planted in a fake tree, to prove the two command lists still fire.
PLANTED_FILE = "planted.py"
PLANTED_COMMIT = 'subprocess.run(["git", "commit", "-m", "audited"])\n'
PLANTED_INSTALL = 'subprocess.run(["pip", "install", "-r", "requirements.txt"])\n'


def source_files(root: Path = SRC_DIR) -> list[Path]:
    """Return every Python module under a tree, src/ unless a test plants its own."""
    return sorted(root.rglob("*.py"))


def module_name(path: Path, root: Path = SRC_DIR) -> str:
    """Name one source file the way this test reports it: relative to its tree."""
    return path.relative_to(root).as_posix()


def parse(path: Path) -> ast.Module:
    """Parse one source file into a syntax tree."""
    return ast.parse(path.read_text(encoding="utf-8"))


def dotted_name(node: ast.expr) -> str:
    """Return `os.system` for an attribute chain, `exec` for a bare name, else ''."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else ""
    return ""


def called_names(tree: ast.Module) -> set[str]:
    """Return the dotted name of everything the module calls."""
    return {dotted_name(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}


def imported_modules(tree: ast.Module) -> set[str]:
    """Return every module name the file imports, however it imports it."""
    names = {alias.name for node in ast.walk(tree)
             if isinstance(node, ast.Import) for alias in node.names}
    return names | {node.module for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom) and node.module}


def string_literals(tree: ast.Module) -> list[str]:
    """Return every string written in the module, docstrings included."""
    return [node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)]


def modules_containing(names: frozenset[str]) -> set[str]:
    """Return the source modules that call any of the given names."""
    return {module_name(path) for path in source_files()
            if called_names(parse(path)) & names}


def modules_mentioning(commands: tuple[str, ...], root: Path = SRC_DIR) -> dict[str, str]:
    """Return each module under a tree that writes one of these command strings, and which."""
    found = {}
    for path in source_files(root):
        literals = " ".join(string_literals(parse(path))).lower()
        hits = [command for command in commands if command in literals]
        if hits:
            found[module_name(path, root)] = hits[0]
    return found


def test_the_source_tree_was_actually_scanned() -> None:
    """Guard: the checks below say nothing if the file list came back empty."""
    assert len(source_files()) > 10
    assert GENERATOR_MODULE in {module_name(path) for path in source_files()}


def test_no_module_names_a_command_that_rewrites_a_repository() -> None:
    """Nothing in src/ spells a git commit, push, merge or a pull request."""
    assert modules_mentioning(MUTATING_COMMANDS) == {}


def test_no_module_names_a_command_that_installs_or_starts_the_audited_app() -> None:
    """Phase 3 reads the corpus app; it never installs its packages or runs it."""
    assert modules_mentioning(EXECUTION_COMMANDS) == {}


def test_only_the_sbom_generator_module_starts_a_process() -> None:
    """Exactly one module may launch anything, and it is the one that runs Syft."""
    assert modules_containing(PROCESS_LAUNCHERS) == {GENERATOR_MODULE}


def test_the_generator_module_launches_syft_and_nothing_else() -> None:
    """Its one launch call passes GENERATOR_NAME as the program, not a shell or a git."""
    tree = parse(SRC_DIR / GENERATOR_MODULE)
    launches = [node for node in ast.walk(tree)
                if isinstance(node, ast.Call) and dotted_name(node.func) in PROCESS_LAUNCHERS]
    assert len(launches) == 1
    argv = launches[0].args[0]
    assert isinstance(argv, ast.List)
    assert dotted_name(argv.elts[0]) == "GENERATOR_NAME"
    assert GENERATOR_NAME == "syft"


def test_no_module_imports_the_machinery_for_running_another_program() -> None:
    """`runpy` and `importlib` are how the audited app would get executed; neither is used."""
    used = {module_name(path) for path in source_files()
            if imported_modules(parse(path)) & EXECUTION_IMPORTS}
    assert used == set()


def test_no_module_calls_exec_eval_or_import() -> None:
    """The auditor parses the audited source into a tree; it never evaluates it."""
    assert modules_containing(EXECUTION_CALLS) == set()


def plant_module(tmp_path: Path, source: str) -> Path:
    """Write a throwaway source tree holding one offending module, and return its root."""
    root = tmp_path / "planted_src"
    root.mkdir()
    (root / PLANTED_FILE).write_text(source, encoding="utf-8")
    return root


def test_the_command_matcher_catches_a_planted_git_commit(tmp_path) -> None:
    """Mutation check: run the matcher over a tree that does commit, and see it reported."""
    root = plant_module(tmp_path, PLANTED_COMMIT)
    assert modules_mentioning(MUTATING_COMMANDS, root) == {PLANTED_FILE: "git commit"}


def test_the_command_matcher_catches_a_planted_pip_install(tmp_path) -> None:
    """The same for the execution list: a planted `pip install` must not pass unseen."""
    root = plant_module(tmp_path, PLANTED_INSTALL)
    assert modules_mentioning(EXECUTION_COMMANDS, root) == {PLANTED_FILE: "pip install"}


def test_both_command_lists_are_non_empty() -> None:
    """An emptied tuple matches nothing, so the two clean-tree tests would pass forever."""
    assert len(MUTATING_COMMANDS) > 0
    assert len(EXECUTION_COMMANDS) > 0
