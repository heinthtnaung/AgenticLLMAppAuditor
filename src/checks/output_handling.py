"""Reports a database query assembled by string interpolation instead of parameters.

**What this establishes, and what it does not.** It establishes the *sink* half
of LLM02: a query whose text is built at runtime, so whatever was interpolated
decides what the database runs. It does **not** establish that the interpolated
value came from the model, which is the other half of "insecure output
handling" -- an f-string yields no `ast.Name` for `parsing.bindings` to bind, so
the taint trace this repo has cannot follow a value into one. Read a finding
here as "this query is built the way an injected value would exploit", not as
"model output reached a database".

**What it cannot see**, which matters because the check is named in
`coverage.checks_run` and `docs/SCHEMAS.md` defines a name there as "looked and
found nothing". Only the argument expression itself is judged, so a query
assembled into a variable one line earlier -- `q = f"SELECT {x}"` then
`cursor.execute(q)` -- is silent, and so is `.format_map(d)`. Both are verified
misses, not speculation, and both are filed in `docs/TODO.md`.

Scoped to LLM applications by the planner rather than by this module: it is
planned only on a repo that has an agent or a tool call, so a plain web app
with the same defect is left to the SAST tools that own CWE-89. On a repo with
no LLM surface the check is absent from `coverage.checks_run` -- "did not look",
not "looked and found nothing".
"""

import ast
from pathlib import Path

from artifacts.finding import STATIC, Finding
from artifacts.skipped_file import UnreadableSource
from artifacts.surface import DATA_SOURCE, Surface
from checks.taint import python_files
from detectors.detector_names import DATA_SOURCE_METHODS
from parsing.ast_utils import call_leaf, call_name
from parsing.extractor_python import parse_file

CHECK_NAME = "unsafe_query_construction"

# LLM02 in the 2023 OWASP list, renumbered LLM05 in 2025. Kept as LLM02 because
# that is the spelling `evaluation/grading.py` scores against and the one the
# grading keys were written in; `retrieval/owasp_reference.py` carries the note.
OWASP_ID = "LLM02"

TITLE = "Database query built by string interpolation, not parameterised"

# The methods a finding can be anchored on. Only these two, because the anchor
# is a `DATA_SOURCE` surface and the detector table below is what produces one:
# naming a third would claim coverage no surface can supply. `executescript`
# is the one worth adding, and needs a detector change of its own -- see
# `docs/TODO.md`.
EXECUTE_METHODS = frozenset({"execute", "executemany"})

if not EXECUTE_METHODS <= set(DATA_SOURCE_METHODS):
    raise ValueError(
        f"EXECUTE_METHODS {sorted(EXECUTE_METHODS)} must all be in DATA_SOURCE_METHODS "
        f"{sorted(DATA_SOURCE_METHODS)}, or no surface can anchor the finding")

# `"... %s" % value` and `"..." + value`. Both build the query text before the
# driver sees it, which is what parameterisation exists to prevent.
INTERPOLATING_OPERATORS = (ast.Mod, ast.Add)

# `"SELECT ... {}".format(value)`, the third spelling of the same defect.
FORMAT_METHOD = "format"

# A surface name is the dotted call chain, so the method is its last segment.
NAME_SEPARATOR = "."


def _method_of(surface_name: str) -> str:
    """The method a surface's dotted name ends in: `execute` for `cursor.execute`.

    By segment, not by `endswith`, so `db.preexecute` is not read as `execute`.
    """
    return surface_name.split(NAME_SEPARATOR)[-1]


def _interpolates_a_value(part: ast.expr) -> bool:
    """Say whether one f-string piece puts a runtime value in; `f"{'a'}"` puts in a constant."""
    return isinstance(part, ast.FormattedValue) and not isinstance(part.value, ast.Constant)


def _is_literal_text(query: ast.expr) -> bool:
    """Say whether this expression is written-out text, however many pieces it is in.

    Recursive, because `"a" + "b" + "c"` nests: judging one level deep would
    call two literals safe and three literals dynamic, which is worse than not
    narrowing at all.
    """
    if isinstance(query, ast.Constant):
        return True
    if not isinstance(query, ast.BinOp) or not isinstance(query.op, INTERPOLATING_OPERATORS):
        return False
    return _is_literal_text(query.left) and _is_literal_text(query.right)


def _formats_a_value(query: ast.expr) -> bool:
    """Say whether the query is a `.format(...)` call that was given something to insert."""
    if not isinstance(query, ast.Call) or call_leaf(query) != FORMAT_METHOD:
        return False
    return bool(query.args or query.keywords)


def _is_dynamic(query: ast.expr) -> bool:
    """Say whether this query text was assembled at runtime rather than written out."""
    if isinstance(query, ast.JoinedStr):
        return any(_interpolates_a_value(part) for part in query.values)
    if isinstance(query, ast.BinOp) and isinstance(query.op, INTERPOLATING_OPERATORS):
        return not _is_literal_text(query)
    return _formats_a_value(query)


def _built_by_interpolation(call: ast.Call) -> bool:
    """Judge the first argument, the query text -- the later ones are the parameters.

    `executemany(f"INSERT INTO {table} VALUES (?)", rows)` is the same defect as
    `execute`: parameterising the rows does not parameterise the table name.
    """
    return bool(call.args) and _is_dynamic(call.args[0])


def _dynamic_execute_calls(tree: ast.AST) -> dict[int, set[str]]:
    """Map each line to the dotted names of the interpolated execute calls on it.

    By full name, not by method: `cursor.execute(f"...")` and
    `audit.execute("SELECT 1")` can share a line, and matching on `execute`
    alone would anchor the first call's verdict on the second call's surface.
    """
    found: dict[int, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if call_leaf(node) in EXECUTE_METHODS and _built_by_interpolation(node):
            found.setdefault(node.lineno, set()).add(call_name(node))
    return found


def _execute_surfaces(surfaces: list[Surface], file: str) -> list[Surface]:
    """The file's data-source surfaces that are an execute call, and so can anchor a finding.

    The method filter narrows, it does not guard: `find_in_tree` matches the
    whole dotted name against names whose leaf is already in `EXECUTE_METHODS`,
    so nothing this lets through can match wrongly. Mutating `_method_of` to a
    suffix match changes no result -- the join is the rule.
    """
    return [s for s in surfaces
            if s.file == file and s.kind == DATA_SOURCE
            and _method_of(s.name) in EXECUTE_METHODS]


def _finding_for(surface: Surface) -> Finding:
    """Build the finding, anchored on the surface: that is where a grading key records it."""
    return Finding(
        OWASP_ID, CHECK_NAME, TITLE, STATIC,
        surface_id=surface.id, surface_kind=surface.kind, surface_name=surface.name,
        file=surface.file, line=surface.line,
    )


def find_in_tree(tree: ast.AST, file: str, surfaces: list[Surface]) -> list[Finding]:
    """Report each execute surface in this file whose query text is interpolated.

    A surface is joined to a call by line *and* method name, because a line is
    not a unique join: `open(path)` and `cursor.execute(q)` can share one, and
    the surface at that line may be the other call. A surface no call at its
    line matches reports nothing.
    """
    dynamic = _dynamic_execute_calls(tree)
    # `Finding.id` is `surface_id:rule_id`, so two interpolated calls sharing one
    # line would emit the same id twice and the document would refuse it.
    reported: dict[str, Finding] = {}
    for surface in _execute_surfaces(surfaces, file):
        if surface.name not in dynamic.get(surface.line, set()):
            continue
        finding = _finding_for(surface)
        reported.setdefault(finding.id, finding)
    return list(reported.values())


def run_over_repo(repo_path: str, surfaces: list[Surface]) -> list[Finding]:
    """Read each Python file and report the queries it builds by interpolation.

    Python only, for the same reason as the taint trace: this reads an `ast`
    tree, and the JavaScript side would need the rule rebuilt on tree-sitter.
    """
    root = Path(repo_path)
    findings: list[Finding] = []
    for path in python_files(repo_path):
        try:
            tree = parse_file(path)
        except UnreadableSource:
            # Already recorded in surfaces.json's skipped_files. One unreadable
            # file must not cost the audit -- the guarantee Phase 1 makes.
            continue
        findings += find_in_tree(tree, path.relative_to(root).as_posix(), surfaces)
    return findings
