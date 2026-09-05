"""No module of either baseline names an artifact this project produces.

A baseline built on `surfaces.json`, `mapping.json` or the auditor's `sbom.json`
is not a baseline: it is the auditor with a different front end, and the
comparison would measure two renderings of one system.

Asserted over the source, so it covers every path including the ones a given
run does not take. The other half -- what a real run actually opens -- is in
`test_baseline_reads.py`; each check has a gap the other covers.

Docstrings are excluded from the search. Both baseline modules explain in prose
exactly which artifacts they refuse to read, and a matcher that cannot tell
prose from a path would force them to stop explaining themselves.
"""

import ast
from pathlib import Path

import pytest

from ast_scan import called_names, module_name, parse, source_files
from conftest import SRC_DIR
from test_scorer_boundary import SCORED_TREES

BASELINES_TREE = "baselines"

# The artifacts this project produces. A baseline may not open one, whatever
# directory it sits in.
PROJECT_ARTIFACTS = ("surfaces.json", "mapping.json", "sbom.json", "aibom.json",
                     "findings.json", "evaluation.json")

# The auditor's own joins, which produce the artifacts above. Calling one would
# reach this project's work without opening any file.
PROJECT_JOINS = ("build_sbom", "build_mapping", "build_aibom", "extract_repo",
                 "build_findings", "score_app")

# A module that really does read an artifact, and one that only writes the name
# in its prose, to prove the matcher tells them apart.
PLANTED_FILE = "planted.py"
PLANTED_READER = 'SURFACES = json.loads(open("surfaces.json").read())\n'
PLANTED_DOCSTRING = '"""This baseline never opens surfaces.json."""\n'
PLANTED_ARTIFACT = "surfaces.json"


def docstring_nodes(tree: ast.Module) -> set[int]:
    """Return the id of every node that is a docstring, so prose is not read as a path."""
    holders = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, holders) and node.body and isinstance(node.body[0], ast.Expr):
            found.add(id(node.body[0].value))
    return found


def written_paths(tree: ast.Module) -> list[str]:
    """Return every string the module writes outside a docstring."""
    skip = docstring_nodes(tree)
    return [node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and id(node) not in skip]


def baseline_modules() -> list[Path]:
    """Return every module of the two baselines."""
    return source_files(SRC_DIR / BASELINES_TREE)


@pytest.mark.parametrize("artifact", PROJECT_ARTIFACTS)
def test_no_baseline_module_writes_the_name_of_a_project_artifact(artifact: str) -> None:
    """The path would have to be spelled somewhere to be opened by name."""
    naming = {module_name(path, SRC_DIR) for path in baseline_modules()
              if any(artifact in written for written in written_paths(parse(path)))}
    assert naming == set()


@pytest.mark.parametrize("join", PROJECT_JOINS)
def test_no_baseline_calls_one_of_the_auditors_joins(join: str) -> None:
    """`mapping.json`'s join is the difference the comparison exists to expose."""
    calling = {module_name(path, SRC_DIR) for path in baseline_modules()
               if any(name.endswith(join) for name in called_names(parse(path)))}
    assert calling == set()


def test_the_baselines_were_actually_scanned() -> None:
    """Guard: the assertions above say nothing if the file list came back empty."""
    assert len(baseline_modules()) > 2


def test_the_baseline_tree_is_covered_by_the_scorer_boundary() -> None:
    """`test_scorer_boundary.py` guards the grading key; the tree must stay on its list."""
    assert BASELINES_TREE in SCORED_TREES


def plant(tmp_path: Path, source: str) -> ast.Module:
    """Write one throwaway module and return its parsed tree."""
    path = tmp_path / PLANTED_FILE
    path.write_text(source, encoding="utf-8")
    return parse(path)


def test_the_matcher_catches_a_planted_read_of_an_artifact(tmp_path: Path) -> None:
    """Mutation check: a module that does open one is named by the same matcher."""
    assert PLANTED_ARTIFACT in written_paths(plant(tmp_path, PLANTED_READER))


def test_the_matcher_ignores_the_name_written_in_a_docstring(tmp_path: Path) -> None:
    """The exclusion is what lets the modules keep explaining what they refuse to read."""
    assert written_paths(plant(tmp_path, PLANTED_DOCSTRING)) == []
