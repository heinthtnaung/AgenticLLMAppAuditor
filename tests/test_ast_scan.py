"""There is one copy of each source scanner, and this file is what holds it to that.

Guards throughout this suite read this project's own source instead of running
it -- nothing launches a process, nothing imports `requests`, the scorer reads
no grading key -- and each walks `src/` with the scanners in `ast_scan.py`.
Several docstrings state that one-copy claim in prose, `test_scorer_boundary.py`
among them.

Prose does not fail. While both claims stood, `checks/test_workflow_scope.py`
carried a byte-identical `string_literals` and a `called_names` that answered
differently -- bare `node.func.id`, never the dotted chain -- under the same
name, and every test over it passed. Two functions with one name and two
answers is the whole hazard, so the claim is asserted here rather than
repeated: every function `ast_scan.py` defines must be defined nowhere else
under `tests/`.

The names are read out of `ast_scan.py` itself, so a scanner added there is
covered by the sweep. The rule is about the name, not the body: a second
`def called_names` fails whatever it does, because a reader cannot tell which
one a call meant. A helper that genuinely does something else gets a name that
says so -- the detector helpers' snippet parsers are `parse_snippet`, not a
third `parse`.

Two false alarms are predictable here, and neither of them wants an allowlist.
`defined_names` walks nested definitions, so a closure or a monkeypatch stub
named `parse` inside a test body trips the sweep even though nothing could
confuse it -- the answer there is a name that says what scope it belongs to,
not an exemption. And the skip is `path.name == "ast_scan.py"`, so a second
file of that name in any subdirectory would be exempt from the sweep entirely.
"""

from pathlib import Path

from ast_scan import defined_names, module_name, parse, source_files
from conftest import TESTS_DIR

# The shared module, and a floor under the number of scanners in it. The floor
# is here so an emptied or unparsed scanner list cannot make the sweep below
# pass silently.
SCANNER_FILENAME = "ast_scan.py"
SCANNER_MODULE = TESTS_DIR / SCANNER_FILENAME
MINIMUM_SCANNERS = 13

# The three names the duplicate in test_workflow_scope.py actually used. If the
# sweep stops seeing these, it has stopped seeing the scanners.
ONCE_DUPLICATED = frozenset({"parse", "called_names", "string_literals"})

# A test module with functions of its own, to prove the definition finder reads
# a real file rather than returning nothing.
SAMPLE_MODULE = "test_no_write_commands.py"
SAMPLE_FUNCTION = "plant_module"

# The suite is 170-odd files; the floor only has to be high enough that an
# empty or single-file walk cannot pass.
MINIMUM_TEST_MODULES = 100

# A duplicate planted in a fake tests/ tree, to prove the sweep still fires.
PLANTED_FILE = "test_planted.py"
PLANTED_DUPLICATE = "def string_literals(tree):\n    return []\n"


def scanner_names() -> set[str]:
    """Every function ast_scan.py defines -- the names that may appear nowhere else."""
    return defined_names(parse(SCANNER_MODULE))


def modules_defining(names: set[str], root: Path = TESTS_DIR) -> dict[str, list[str]]:
    """Return, per scanner name, the test modules other than ast_scan.py that define it."""
    found: dict[str, list[str]] = {}
    for path in source_files(root):
        if path.name == SCANNER_FILENAME:
            continue
        for name in sorted(defined_names(parse(path)) & names):
            found.setdefault(name, []).append(module_name(path, root))
    return {name: sorted(paths) for name, paths in sorted(found.items())}


def plant_test_module(tmp_path: Path, source: str) -> Path:
    """Write a throwaway tests/ tree holding one module, and return its root."""
    root = tmp_path / "planted_tests"
    root.mkdir()
    (root / PLANTED_FILE).write_text(source, encoding="utf-8")
    return root


def test_no_other_test_module_defines_a_scanner_name() -> None:
    """The one-copy claim, asserted: `def called_names` exists in ast_scan.py alone."""
    assert modules_defining(scanner_names()) == {}


def test_the_scanner_names_were_read_out_of_the_shared_module() -> None:
    """Guard: an empty name set would make the sweep above pass over anything."""
    names = scanner_names()
    assert len(names) >= MINIMUM_SCANNERS
    assert ONCE_DUPLICATED <= names


def test_the_whole_tests_tree_was_walked() -> None:
    """Guard: the sweep is worth nothing if it looked at one file, or none."""
    walked = {module_name(path, TESTS_DIR) for path in source_files(TESTS_DIR)}
    assert len(walked) > MINIMUM_TEST_MODULES
    assert SAMPLE_MODULE in walked


def test_the_definition_finder_reads_a_real_test_module() -> None:
    """Guard: it finds a function that is really there, so absence means absence."""
    assert SAMPLE_FUNCTION in defined_names(parse(TESTS_DIR / SAMPLE_MODULE))


def test_a_planted_second_copy_of_a_scanner_is_reported(tmp_path) -> None:
    """Mutation check: run the sweep over a tree that does duplicate one, and see it."""
    root = plant_test_module(tmp_path, PLANTED_DUPLICATE)
    assert modules_defining(scanner_names(), root) == {"string_literals": [PLANTED_FILE]}


def test_the_shared_module_is_not_reported_against_itself(tmp_path) -> None:
    """The skip is by filename, so ast_scan.py's own definitions are not the duplicate."""
    root = plant_test_module(tmp_path, PLANTED_DUPLICATE)
    (root / SCANNER_FILENAME).write_text(
        SCANNER_MODULE.read_text(encoding="utf-8"), encoding="utf-8")
    assert modules_defining(scanner_names(), root) == {"string_literals": [PLANTED_FILE]}
