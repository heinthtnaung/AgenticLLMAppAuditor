"""The answer key flows one way: into the scorer, and never back into the tool.

`SCHEMAS.md` states it -- `evaluation.json` is never an input to anything under
`src/checks/`, `src/detectors/` or `src/artifacts/`, and the scorer is the
first component allowed to read the key's ids. A tool that can see which
entries it missed can be tuned until it misses none, and every number after
that measures the tuning.

Like test_no_write_commands.py this is asserted over the source rather than by
running anything: a path that was not taken looks exactly like one that does
not exist. The `ast` scanners come from ast_scan.py, shared with every other
guard that reads this project's own source -- one copy of the parsing, so every
boundary is read the same way.
"""

from pathlib import Path

from ast_scan import (
    imported_modules,
    module_name,
    parse,
    source_files,
    string_literals,
)
from conftest import SRC_DIR

# The trees that make up the tool being scored. The scorer sits outside them.
# `retrieval` is here because `checks/advise.py` is fed by it: a tree the
# guard skipped would be the one a grading-key read could route through.
SCORED_TREES = ("checks", "detectors", "artifacts", "baselines", "retrieval")

# What none of them may read: the scorecard, and the module that writes it.
EVALUATION_NAME = "evaluation.json"
SCORER_PACKAGE = "evaluation"

# The grading key itself, which carries the hand-authored ids the tool must not see.
GROUND_TRUTH_NAME = "ground_truth.json"

# The module that locates every grading key. It was `corpus_paths` until the
# pinned corpus was removed; the name is spelled once here because the guard
# below is vacuous against a module that does not exist.
KEYS_PACKAGE = "grading_keys"

# A planted module, to prove the matcher below fires on a real violation.
PLANTED_FILE = "planted.py"
PLANTED_READER = 'MISSES = json.loads(open("evaluation.json").read())\n'
PLANTED_IMPORT = "from evaluation.scorer import score_app\n"
PLANTED_KEYS_IMPORT = "from grading_keys import GROUND_TRUTH_SUFFIX, key_path\n"


def scored_trees() -> list[Path]:
    """Return the root of each tree that makes up the tool being scored."""
    return [SRC_DIR / name for name in SCORED_TREES]


def modules_naming(text: str, root: Path) -> set[str]:
    """Return the modules under a tree that write a given string anywhere in their source."""
    return {module_name(path, root) for path in source_files(root)
            if any(text in literal for literal in string_literals(parse(path)))}


def modules_importing(package: str, root: Path) -> set[str]:
    """Return the modules under a tree that import a package, or anything inside it."""
    return {module_name(path, root) for path in source_files(root)
            if any(name == package or name.startswith(f"{package}.")
                   for name in imported_modules(parse(path)))}


def scored_modules_naming(text: str) -> set[str]:
    """Search every tree the scorer grades for a written string."""
    found: set[str] = set()
    for root in scored_trees():
        found |= modules_naming(text, root)
    return found


def scored_modules_importing(package: str) -> set[str]:
    """Search every tree the scorer grades for an import of a package."""
    found: set[str] = set()
    for root in scored_trees():
        found |= modules_importing(package, root)
    return found


def test_the_scored_trees_were_actually_scanned() -> None:
    """Guard: the assertions below say nothing if a file list came back empty."""
    counts = [len(source_files(root)) for root in scored_trees()]
    assert min(counts) > 0
    assert sum(counts) > 10


def test_no_scored_module_names_the_evaluation_artifact() -> None:
    """A check that reads its own scorecard is a check tuned against the key."""
    assert scored_modules_naming(EVALUATION_NAME) == set()


def test_no_scored_module_names_the_grading_key() -> None:
    """The key's hand-authored ids are Phase 4's to read, not the tool's."""
    assert scored_modules_naming(GROUND_TRUTH_NAME) == set()


def test_no_scored_module_imports_the_scorer() -> None:
    """Importing it would reach the key by a different route than opening the file."""
    assert scored_modules_importing(SCORER_PACKAGE) == set()


def test_the_scorer_is_the_component_that_holds_the_join() -> None:
    """The dependency runs the other way: the scorer imports the shared join rule."""
    imported = imported_modules(parse(SRC_DIR / SCORER_PACKAGE / "scorer.py"))
    assert "evaluation.grading" in imported


def plant_tree(tmp_path: Path, source: str) -> Path:
    """Write a throwaway source tree holding one offending module, and return its root."""
    root = tmp_path / "planted_src"
    root.mkdir()
    (root / PLANTED_FILE).write_text(source, encoding="utf-8")
    return root


def test_the_matcher_catches_a_planted_read_of_the_scorecard(tmp_path) -> None:
    """Mutation check: run it over a module that does read the file, and see it named."""
    assert modules_naming(EVALUATION_NAME, plant_tree(tmp_path, PLANTED_READER)) == {PLANTED_FILE}


def test_the_matcher_catches_a_planted_import_of_the_scorer(tmp_path) -> None:
    """The same for the import route, which no string check would see."""
    planted = plant_tree(tmp_path, PLANTED_IMPORT)
    assert modules_importing(SCORER_PACKAGE, planted) == {PLANTED_FILE}


def test_the_keys_module_this_guard_names_really_exists() -> None:
    """Guard on the guard: an import check against a renamed module is vacuously true.

    This assertion was written as `scored_modules_importing("corpus_paths")`
    and kept passing after that module became `grading_keys` -- silently
    guarding nothing. The name is checked against the filesystem so the rename
    fails here instead.
    """
    assert (SRC_DIR / f"{KEYS_PACKAGE}.py").is_file()


def test_no_scored_module_imports_the_grading_key_locator() -> None:
    """A scored tree may not reach the keys, and naming the file is not enough.

    The string check above catches a module that writes "ground_truth.json".
    `grading_keys` exposes `key_path` and `GROUND_TRUTH_SUFFIX`, so a module
    importing it reaches every grading key without ever writing that string --
    which is exactly how a baseline could quietly score itself.
    """
    assert scored_modules_importing(KEYS_PACKAGE) == set()


def test_the_matcher_catches_a_planted_import_of_the_keys_module(tmp_path) -> None:
    """Mutation check the assertion above never had: plant the import and see it named."""
    planted = plant_tree(tmp_path, PLANTED_KEYS_IMPORT)
    assert modules_importing(KEYS_PACKAGE, planted) == {PLANTED_FILE}


def test_the_scorer_never_opens_the_remediation_artifact() -> None:
    """Model prose must stay structurally unable to reach a score.

    The design rests on the scorer opening three files and `remediation.json`
    not being one of them, so no word a model wrote can enter a number. That
    is stated in `SCHEMAS.md`, `FLOW.md`, the README and the module docstring,
    and until now was pinned by nothing: adding the file to `harness.py` passed
    every test.
    """
    assert modules_naming("remediation.json", SRC_DIR / "evaluation") == set()
    assert modules_importing("artifacts.remediation", SRC_DIR / "evaluation") == set()
