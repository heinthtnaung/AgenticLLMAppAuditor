"""Small shared helpers for reading Python syntax trees."""

import ast


def dotted_name(node: ast.expr) -> str:
    """Return the dotted source name of an expression, or '' if it is not a plain name."""
    if isinstance(node, ast.Name):
        return node.id
    if not isinstance(node, ast.Attribute):
        return ""
    parent = dotted_name(node.value)
    return f"{parent}.{node.attr}" if parent else node.attr


def call_name(node: ast.Call) -> str:
    """Return what a call invokes, e.g. 'ChatPromptTemplate.from_messages'."""
    return dotted_name(node.func)


def call_root(node: ast.Call) -> str:
    """Return the leftmost name of a call, e.g. 'ChatPromptTemplate'."""
    return call_name(node).split(".")[0]


def call_leaf(node: ast.Call) -> str:
    """Return the final attribute of a call, e.g. 'from_messages'."""
    return call_name(node).split(".")[-1]


def keyword_string(node: ast.Call, keyword: str) -> str:
    """Return a string keyword argument's literal value, or '' if it is not one."""
    for given in node.keywords:
        if given.arg != keyword:
            continue
        if isinstance(given.value, ast.Constant) and isinstance(given.value.value, str):
            return given.value.value
    return ""


def decorator_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Return the dotted names of a function's decorators, ignoring their arguments."""
    names = []
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        names.append(dotted_name(target))
    return names


def assigned_name(node: ast.Assign) -> str:
    """Return the single variable an assignment targets, or '' if it is not a simple one."""
    if len(node.targets) != 1:
        return ""
    target = node.targets[0]
    return target.id if isinstance(target, ast.Name) else ""


def is_text_value(node: ast.expr) -> bool:
    """Say whether an expression is a plain string or an f-string."""
    if isinstance(node, ast.JoinedStr):
        return True
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def text_build_shape(value: ast.expr) -> str:
    """Name how an expression builds text, or '' if it does not build text at all."""
    if isinstance(value, ast.JoinedStr):
        return "f-string"
    if is_text_value(value):
        return "string"
    if isinstance(value, ast.Call) and call_leaf(value) == "format":
        return "formatted string"
    if not isinstance(value, ast.BinOp) or not isinstance(value.op, ast.Add):
        return ""
    if is_text_value(value.left) or is_text_value(value.right):
        return "concatenated string"
    return ""


def _record_import_from(node: ast.ImportFrom, table: dict[str, str]) -> None:
    """Record 'from x.y import a as b' as b -> x.y.

    A relative import (`from .settings import ...`) is the app's own code, not a
    package, so it records no module rather than a name that looks third-party.
    """
    if node.level:
        return
    for alias in node.names:
        table[alias.asname or alias.name] = node.module or ""


def _record_import(node: ast.Import, table: dict[str, str]) -> None:
    """Record 'import x.y as z' as z -> x.y."""
    for alias in node.names:
        table[alias.asname or alias.name.split(".")[0]] = alias.name


def build_import_table(tree: ast.AST) -> dict[str, str]:
    """Map each name imported in a file to the module it came from."""
    table: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            _record_import_from(node, table)
        if isinstance(node, ast.Import):
            _record_import(node, table)
    return table
