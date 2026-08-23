"""The four independent detectors that find LLM surfaces in one syntax tree."""

import ast

from parsing.ast_utils import (
    assigned_name,
    build_import_table,
    call_leaf,
    call_name,
    call_root,
    decorator_names,
    dotted_name,
    keyword_string,
    text_build_shape,
)
from detectors.detector_names import (
    AGENT_FACTORIES,
    DATA_SOURCE_CALLS,
    DATA_SOURCE_METHODS,
    HIGH_PRIVILEGE_TOOLS,
    HTTP_METHODS,
    MODEL_CLASSES,
    PROMPT_CLASSES,
    PROMPT_NAME_HINTS,
    ROUTE_DECORATOR_ROOTS,
    TOOL_CLASSES,
    TOOL_DECORATORS,
)
from parsing.languages import PYTHON
from artifacts.surface import AGENT_DEF, DATA_SOURCE, PROMPT_TEMPLATE, TOOL_CALL, Surface

FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


# --- Prompt templates ------------------------------------------------------
def _prompt_from_call(node: ast.AST, file: str, imports: dict[str, str]) -> Surface | None:
    """Report a prompt built by a framework prompt class."""
    if not isinstance(node, ast.Call):
        return None
    root = call_root(node)
    if root not in PROMPT_CLASSES:
        return None
    detail = f"{root} constructed here"
    return Surface(PROMPT_TEMPLATE, call_name(node), file, node.lineno, PYTHON,
                   detail=detail, module=imports.get(root, ""))


def _prompt_from_assignment(node: ast.AST, file: str) -> Surface | None:
    """Report prompt text assigned to a prompt-shaped variable name."""
    if not isinstance(node, ast.Assign):
        return None
    name = assigned_name(node)
    if not name or not any(hint in name.lower() for hint in PROMPT_NAME_HINTS):
        return None
    shape = text_build_shape(node.value)
    if not shape:
        return None
    return Surface(PROMPT_TEMPLATE, name, file, node.lineno, PYTHON, detail=f"prompt {shape} assigned to {name}")


def find_prompt_templates(tree: ast.AST, file: str) -> list[Surface]:
    """Find prompt template constructors and prompt-shaped string assignments."""
    imports = build_import_table(tree)
    found = []
    for node in ast.walk(tree):
        surface = _prompt_from_call(node, file, imports) or _prompt_from_assignment(node, file)
        if surface is not None:
            found.append(surface)
    return found


# --- Agent definitions -----------------------------------------------------
def _agent_from_call(node: ast.AST, file: str, imports: dict[str, str]) -> Surface | None:
    """Report an agent, chain, or model client being constructed."""
    if not isinstance(node, ast.Call):
        return None
    root = call_root(node)
    if root not in AGENT_FACTORIES and root not in MODEL_CLASSES:
        return None
    if root in AGENT_FACTORIES:
        detail = f"agent or chain built by {root}"
    else:
        detail = f"model client {root} instantiated"
    name = call_name(node)
    return Surface(AGENT_DEF, name, file, node.lineno, PYTHON, detail=detail, module=imports.get(root, ""))


def find_agent_defs(tree: ast.AST, file: str) -> list[Surface]:
    """Find agent, chain, and model-client constructors."""
    imports = build_import_table(tree)
    found = []
    for node in ast.walk(tree):
        surface = _agent_from_call(node, file, imports)
        if surface is not None:
            found.append(surface)
    return found


# --- Tool definitions ------------------------------------------------------
def _tool_from_function(node: ast.AST, file: str) -> Surface | None:
    """Report a function exposed to the model with a tool decorator."""
    if not isinstance(node, FUNCTION_NODES):
        return None
    matched = [name for name in decorator_names(node) if name in TOOL_DECORATORS]
    if not matched:
        return None
    return Surface(TOOL_CALL, node.name, file, node.lineno, PYTHON, detail=f"function decorated with @{matched[0]}")


def _tool_from_call(node: ast.AST, file: str, imports: dict[str, str]) -> Surface | None:
    """Report a tool object built from a framework tool class."""
    if not isinstance(node, ast.Call):
        return None
    root = call_root(node)
    if root not in TOOL_CLASSES:
        return None
    detail = f"{root} tool defined"
    if root in HIGH_PRIVILEGE_TOOLS:
        detail = f"{root} tool defined - grants shell, code, or network reach"
    name = keyword_string(node, "name") or call_name(node)
    return Surface(TOOL_CALL, name, file, node.lineno, PYTHON, detail=detail, module=imports.get(root, ""))


def _tool_from_class(node: ast.AST, file: str) -> Surface | None:
    """Report a class that subclasses a framework tool base."""
    if not isinstance(node, ast.ClassDef):
        return None
    bases = [dotted_name(base).split(".")[-1] for base in node.bases]
    matched = [base for base in bases if base in TOOL_CLASSES]
    if not matched:
        return None
    return Surface(TOOL_CALL, node.name, file, node.lineno, PYTHON, detail=f"class subclassing {matched[0]}")


def find_tool_calls(tree: ast.AST, file: str) -> list[Surface]:
    """Find tool definitions: decorated functions, tool constructors, tool subclasses."""
    imports = build_import_table(tree)
    found = []
    for node in ast.walk(tree):
        surface = (
            _tool_from_function(node, file)
            or _tool_from_call(node, file, imports)
            or _tool_from_class(node, file)
        )
        if surface is not None:
            found.append(surface)
    return found


# --- Data sources ----------------------------------------------------------
def _source_from_call(node: ast.AST, file: str, imports: dict[str, str]) -> Surface | None:
    """Report a call that reads data from outside the program."""
    if not isinstance(node, ast.Call):
        return None
    name = call_name(node)
    module = imports.get(call_root(node), "")
    if name in DATA_SOURCE_CALLS:
        return Surface(DATA_SOURCE, name, file, node.lineno, PYTHON, detail=DATA_SOURCE_CALLS[name], module=module)
    leaf = call_leaf(node)
    if leaf not in DATA_SOURCE_METHODS:
        return None
    return Surface(DATA_SOURCE, name, file, node.lineno, PYTHON, detail=DATA_SOURCE_METHODS[leaf], module=module)


def _source_from_route(node: ast.AST, file: str) -> Surface | None:
    """Report a web route handler, which receives untrusted request input."""
    if not isinstance(node, FUNCTION_NODES):
        return None
    for decorator in decorator_names(node):
        root, _, method = decorator.partition(".")
        if root in ROUTE_DECORATOR_ROOTS and method in HTTP_METHODS:
            shape = "route" if method == "route" else f"{method} route"
            return Surface(DATA_SOURCE, node.name, file, node.lineno, PYTHON, detail=f"http {shape} input")
    return None


def find_data_sources(tree: ast.AST, file: str) -> list[Surface]:
    """Find the sites where outside data enters: files, requests, retrieval, routes.

    Phase 1 records source sites only. Tracing whether they reach a prompt or a
    tool is Phase 3's taint probe, deliberately not done here.
    """
    imports = build_import_table(tree)
    found = []
    for node in ast.walk(tree):
        surface = _source_from_call(node, file, imports) or _source_from_route(node, file)
        if surface is not None:
            found.append(surface)
    return found
