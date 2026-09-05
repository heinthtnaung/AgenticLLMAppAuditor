"""The tool's published command surface, pinned in both directions.

Nine modules under `src/` carry an `if __name__ == "__main__":` block, and each
one is a command a reader is told to type. Nothing asserted that until now, and
the gap was not theoretical: a planned restructure counted six entry points,
because six is how many the README lists in one place, and would have moved
`fetch_repo.py` -- a documented command -- on the strength of that count.

So this file states the surface twice over, and fails loudly in whichever
direction it breaks:

* a module grew a `__main__` block and nobody published it, or a listed entry
  point lost one (a move counts as losing one -- the scan walks the whole tree
  and names modules by their path under `src/`, so `reporting/emit_vex.py` is a
  different module from `emit_vex.py`);
* a command stopped being documented, or the docs invoke a path that no longer
  runs anything.

The docs side reads whatever `README.md` and `docs/*.md` exist at the time,
never a fixed filename, because the docs are being reorganised -- seven
`PHASE_*_PLAN.md` files, `ADVISORY_PLAN.md` and `RAG_PLAN.md` were merged into
`docs/HISTORY.md` on 2026-09-05. Moving a command's documentation between files
is fine; dropping it is what fails.

The `__main__` detector is defined here rather than in `ast_scan.py`: this is
its only caller, and `test_ast_scan.py` holds that shared module to one copy of
each scanner. It reuses `parse`, `source_files` and `module_name` from there.
"""

import ast
import re
from pathlib import Path

from ast_scan import module_name, parse, source_files
from conftest import REPO_ROOT, SRC_DIR

# The tool's published command surface: every module run as `python src/<path>`.
# Nine, not six -- `ai_report.py` and `model_client.py` are commands too.
ENTRY_POINTS = frozenset({
    "main.py",
    "evaluate.py",
    "run_baseline.py",
    "emit_vex.py",
    "export_reports.py",
    "index_knowledge.py",
    "fetch_repo.py",
    "model_client.py",
    "ai_report.py",
})

# How a doc spells a command, and the prefix a module path gets to become one.
COMMAND_PATTERN = re.compile(r"python\s+src/([\w./-]+\.py)")
COMMAND_PREFIX = "src/"

# Where the docs live. Globbed, not listed, so a renamed doc file is not a hole.
DOC_ROOTS = (REPO_ROOT / "README.md", REPO_ROOT / "docs")

# Floors, so neither sweep can pass over nothing. src/ is 80-odd modules and
# there are 8 documents; these only have to rule out an empty or one-file walk.
MINIMUM_SRC_MODULES = 50
MINIMUM_DOC_FILES = 5

# Modules that must show up in the scan for it to have looked where it claims:
# one at the top of src/, one nested a folder deep. Neither is an entry point.
SCANNED_TOP_LEVEL = "config.py"
SCANNED_NESTED = "parsing/extractor.py"

# A command that must stay documented for the docs sweep to be believable.
SAMPLE_COMMAND = "main.py"

# Sources planted in a fake tree, to prove each sweep really fires.
PLANTED_WITH_MAIN = 'import sys\n\nif __name__ == "__main__":\n    sys.exit(0)\n'
PLANTED_WITHOUT_MAIN = '"""No command here."""\n\nNAME = "__main__"\n'
PLANTED_DOC = "Run `python src/planted.py path/to/app` to plant something.\n"


def has_main_block(tree: ast.Module) -> bool:
    """True if the module guards code with `if __name__ == "__main__":`."""
    return any(isinstance(node, ast.If) and _tests_dunder_name(node.test)
               for node in ast.walk(tree))


def _tests_dunder_name(test: ast.expr) -> bool:
    """True if one `if` condition compares `__name__` against "__main__"."""
    if not isinstance(test, ast.Compare) or not isinstance(test.left, ast.Name):
        return False
    if test.left.id != "__name__":
        return False
    return any(isinstance(other, ast.Constant) and other.value == "__main__"
               for other in test.comparators)


def modules_with_main_block(root: Path = SRC_DIR) -> set[str]:
    """The path, under the tree, of every module that can be run as a command."""
    return {module_name(path, root) for path in source_files(root)
            if has_main_block(parse(path))}


def doc_files(roots: tuple[Path, ...] = DOC_ROOTS) -> list[Path]:
    """Every Markdown file a command could be documented in, whatever it is called."""
    found: list[Path] = []
    for root in roots:
        found.extend(sorted(root.rglob("*.md")) if root.is_dir() else [root])
    return [path for path in found if path.is_file()]


def documented_commands(roots: tuple[Path, ...] = DOC_ROOTS) -> set[str]:
    """Every module path the docs tell a reader to run, as `python src/<path>`."""
    return {match for path in doc_files(roots)
            for match in COMMAND_PATTERN.findall(path.read_text(encoding="utf-8"))}


def test_no_unpublished_module_has_a_main_block() -> None:
    """A module runnable as a command must be on the published list."""
    unpinned = sorted(modules_with_main_block() - ENTRY_POINTS)
    assert not unpinned, (
        "code has a __main__ block the entry-point list does not: "
        f"{unpinned}. Add it to ENTRY_POINTS and document it, or delete the block.")


def test_every_published_entry_point_still_has_a_main_block() -> None:
    """A listed command must still be runnable -- a move counts as gone."""
    missing = sorted(ENTRY_POINTS - modules_with_main_block())
    assert not missing, (
        "the entry-point list names modules src/ no longer runs: "
        f"{missing}. They were moved, renamed or lost their __main__ block.")


def test_every_entry_point_is_documented_as_a_command() -> None:
    """Every command the code offers is spelled out in README.md or docs/."""
    undocumented = sorted(ENTRY_POINTS - documented_commands())
    assert not undocumented, (
        "code has these commands, the docs do not mention them: "
        f"{[COMMAND_PREFIX + name for name in undocumented]}. "
        "Document each as `python src/<path>` or drop the command.")


def test_no_documented_command_is_missing_from_the_code() -> None:
    """The docs may not publish a command that nothing under src/ answers."""
    unbacked = sorted(documented_commands() - ENTRY_POINTS)
    assert not unbacked, (
        "the docs publish these commands, the code does not: "
        f"{[COMMAND_PREFIX + name for name in unbacked]}. "
        "A module was moved or renamed under it, or the doc is stale.")


def test_the_entry_point_list_is_not_empty() -> None:
    """Guard: an emptied list would make both sweeps above pass over nothing."""
    assert len(ENTRY_POINTS) == 9
    assert SAMPLE_COMMAND in ENTRY_POINTS


def test_the_source_sweep_walked_the_whole_src_tree() -> None:
    """Guard: the __main__ sweep is worth nothing if it read one file, or none."""
    walked = {module_name(path) for path in source_files()}
    assert len(walked) > MINIMUM_SRC_MODULES
    assert {SCANNED_TOP_LEVEL, SCANNED_NESTED} <= walked


def test_the_docs_sweep_read_real_documents() -> None:
    """Guard: a missing docs tree must fail loudly, not report nothing documented."""
    assert len(doc_files()) >= MINIMUM_DOC_FILES
    assert SAMPLE_COMMAND in documented_commands()


def test_a_planted_main_block_is_found_and_one_without_is_not(tmp_path: Path) -> None:
    """Mutation check: run the source sweep over a tree whose answer is known."""
    (tmp_path / "planted.py").write_text(PLANTED_WITH_MAIN, encoding="utf-8")
    (tmp_path / "quiet.py").write_text(PLANTED_WITHOUT_MAIN, encoding="utf-8")
    assert modules_with_main_block(tmp_path) == {"planted.py"}


def test_a_planted_command_is_read_out_of_a_document(tmp_path: Path) -> None:
    """Mutation check: run the docs sweep over a document whose answer is known."""
    (tmp_path / "GUIDE.md").write_text(PLANTED_DOC, encoding="utf-8")
    assert documented_commands((tmp_path,)) == {"planted.py"}
