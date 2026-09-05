"""Reading this project's own source with `ast`, for the guards that assert over it.

Several tests state a rule about `src/` as a negative -- nothing launches a
process, nothing imports `requests`, nothing spells `git commit`, the scorer
reads no artifact -- and a negative cannot be shown by running the tool: a code
path that was not taken looks identical to one that does not exist. Each of
those guards walks the source instead, so each needs the same handful of
scanners: list the modules, parse one, name it, and pull out what it imports,
calls, subscripts, defines or writes as a string.

Those scanners lived in `test_no_write_commands.py` until ten other test
modules imported them from it. A test module is not a helper library: importing
one drags in its collection, its constants and its own assertions, and the
functions stop being anyone's clear responsibility. They live here instead,
beside the other `tests/*_helpers.py` and `tests/*_fixtures.py` modules, so
there is exactly one copy of each scanner -- two copies is how the two copies
come to disagree. `test_ast_scan.py` asserts that rather than leaving it here
as prose: it re-reads the names below and fails if any test module defines one
of them again.

Nothing here asserts anything. Every function is a pure read: it takes a path
or a tree and returns names, keys or literals. The rules themselves stay in the
test modules that own them.
"""

import ast
from pathlib import Path

from conftest import SRC_DIR


def source_files(root: Path = SRC_DIR) -> list[Path]:
    """Return every Python module under a tree, src/ unless a test plants its own."""
    return sorted(root.rglob("*.py"))


def module_name(path: Path, root: Path = SRC_DIR) -> str:
    """Name one source file the way these guards report it: relative to its tree."""
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


def defined_names(tree: ast.Module) -> set[str]:
    """Return the name of every function the module defines, nested ones included."""
    return {node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def imported_modules(tree: ast.Module) -> set[str]:
    """Return every module name the file imports, however it imports it."""
    names = {alias.name for node in ast.walk(tree)
             if isinstance(node, ast.Import) for alias in node.names}
    return names | {node.module for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom) and node.module}


def subscript_keys(tree: ast.Module, variable: str) -> set[str]:
    """Return the string keys a module subscripts one variable with, as in `key["source"]`."""
    return {node.slice.value for node in ast.walk(tree)
            if isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name) and node.value.id == variable
            and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str)}


def get_call_keys(tree: ast.Module, variable: str) -> set[str]:
    """Return the string keys a module `.get()`-tests one variable with, as in `e.get("line")`."""
    return {node.args[0].value for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get" and node.args
            and isinstance(node.func.value, ast.Name) and node.func.value.id == variable
            and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)}


def string_literals(tree: ast.Module) -> list[str]:
    """Return every string written in the module, docstrings included."""
    return [node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)]


def _docstring_ids(tree: ast.Module) -> set[int]:
    """The id() of every docstring node, so prose can be told from a value."""
    holders = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, holders) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                found.add(id(first.value))
    return found


def _value_literals(tree: ast.Module) -> list[str]:
    """Every string a module uses as a *value*, docstrings excluded.

    The distinction earns its keep twice: a docstring explaining why this
    project never claims `not_affected`, or why a format is written elsewhere,
    is the opposite of a violation -- while the same text reaching a program as
    an argument is the violation itself.
    """
    skip = _docstring_ids(tree)
    return [node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and id(node) not in skip]


def modules_using_value(token: str, root: Path = SRC_DIR) -> set[str]:
    """The modules under a tree that use a token as a *value*, not in prose.

    Shared by the two guards that need it -- the VEX folder's and the
    forbidden-claims one -- because two copies of a scanner is how the two
    copies come to disagree.

    The comparison is case-sensitive, deliberately: both callers search for
    something a module could *use* -- a path, a filename, a program, a status
    string -- and those are written in the case they are spelled in.
    """
    return {module_name(path, root) for path in source_files(root)
            if any(token in literal for literal in _value_literals(parse(path)))}
