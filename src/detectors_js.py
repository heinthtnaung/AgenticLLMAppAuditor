"""The four surface detectors for JavaScript and TypeScript syntax trees.

The tree-sitter mirror of detectors.py. Same four surface kinds, same name-table
approach, so the two backends stay recognisably the same shape.
"""

from tree_sitter import Node

from detector_names_js import (
    AGENT_FACTORIES,
    DATA_SOURCE_CALLS,
    DATA_SOURCE_MEMBERS,
    DATA_SOURCE_METHODS,
    HIGH_PRIVILEGE_TOOLS,
    MODEL_CLASSES,
    MESSAGE_ROLE_KEY,
    MESSAGE_TEXT_KEYS,
    PROMPT_CLASSES,
    PROMPT_NAME_HINTS,
    TOOL_CLASSES,
    TOOL_FACTORIES,
)
from languages import language_of
from surface import AGENT_DEF, DATA_SOURCE, PROMPT_TEMPLATE, TOOL_CALL, Surface
from ts_utils import (
    CALL_NODES,
    build_import_table,
    call_name,
    call_root,
    declared_name,
    line_of,
    node_text,
    text_shape,
    walk,
)

# A declaration binds a name to a value: `const systemPrompt = ...`.
DECLARATOR = "variable_declarator"
TEXT_NODES = ("template_string", "string")


# --- Prompt templates ------------------------------------------------------
def _prompt_from_call(node: Node, source: bytes, file: str, imports: dict) -> Surface | None:
    """Report a prompt built by a framework prompt class."""
    if node.type not in CALL_NODES:
        return None
    root = call_root(node, source)
    if root not in PROMPT_CLASSES:
        return None
    return _surface(PROMPT_TEMPLATE, call_name(node, source), file, node,
                    f"{root} constructed here", imports.get(root, ""))


def _prompt_from_declaration(node: Node, source: bytes, file: str) -> Surface | None:
    """Report text assigned to a prompt-shaped variable name."""
    if node.type != DECLARATOR:
        return None
    name = declared_name(node, source)
    if not name or not any(hint in name.lower() for hint in PROMPT_NAME_HINTS):
        return None
    value = node.child_by_field_name("value")
    shape = text_shape(value) if value is not None else ""
    if not shape:
        return None
    return _surface(PROMPT_TEMPLATE, name, file, node, f"prompt {shape} assigned to {name}", "")


def _pair_key(node: Node, source: bytes) -> str:
    """Return an object property's key name."""
    key = node.child_by_field_name("key")
    return node_text(key, source).strip("\"'") if key is not None else ""


def _sibling_role(node: Node, source: bytes) -> str:
    """Return the role of the chat message a property belongs to, or ''."""
    if node.parent is None:
        return ""
    for sibling in node.parent.children:
        if sibling.type == "pair" and _pair_key(sibling, source) == MESSAGE_ROLE_KEY:
            value = sibling.child_by_field_name("value")
            return node_text(value, source).strip("\"'") if value is not None else ""
    return ""


def _prompt_from_message(node: Node, source: bytes, file: str) -> Surface | None:
    """Report prompt text written inline as a chat message, e.g. {role, content}."""
    if node.type != "pair":
        return None
    key = _pair_key(node, source)
    value = node.child_by_field_name("value")
    if value is None or not text_shape(value):
        return None
    role = _sibling_role(node, source)
    if key in MESSAGE_TEXT_KEYS and role:
        return _surface(PROMPT_TEMPLATE, f"{role}_message", file, node,
                        f"inline {role} message, {text_shape(value)}", "")
    if any(hint in key.lower() for hint in PROMPT_NAME_HINTS):
        return _surface(PROMPT_TEMPLATE, key, file, node,
                        f"prompt {text_shape(value)} assigned to {key}", "")
    return None


def find_prompt_templates(tree: Node, file: str, source: bytes) -> list[Surface]:
    """Find prompt template constructors and prompt-shaped text declarations."""
    imports = build_import_table(tree, source)
    found = []
    for node in walk(tree):
        surface = (_prompt_from_call(node, source, file, imports)
                   or _prompt_from_declaration(node, source, file)
                   or _prompt_from_message(node, source, file))
        if surface is not None:
            found.append(surface)
    return found


# --- Agent definitions -----------------------------------------------------
def find_agent_defs(tree: Node, file: str, source: bytes) -> list[Surface]:
    """Find agent, graph, and model-client constructors."""
    imports = build_import_table(tree, source)
    found = []
    for node in walk(tree):
        if node.type not in CALL_NODES:
            continue
        root = call_root(node, source)
        if root in AGENT_FACTORIES:
            detail = f"agent or graph built by {root}"
        elif root in MODEL_CLASSES:
            detail = f"model client {root} instantiated"
        else:
            continue
        found.append(_surface(AGENT_DEF, call_name(node, source), file, node,
                              detail, imports.get(root, "")))
    return found


# --- Tool definitions ------------------------------------------------------
def find_tool_calls(tree: Node, file: str, source: bytes) -> list[Surface]:
    """Find tool definitions: framework tool classes and tool factory calls."""
    imports = build_import_table(tree, source)
    found = []
    for node in walk(tree):
        if node.type not in CALL_NODES:
            continue
        root = call_root(node, source)
        if root not in TOOL_CLASSES and root not in TOOL_FACTORIES:
            continue
        detail = f"{root} tool defined"
        if root in HIGH_PRIVILEGE_TOOLS:
            detail = f"{root} tool defined - grants shell, code, or network reach"
        found.append(_surface(TOOL_CALL, call_name(node, source), file, node,
                              detail, imports.get(root, "")))
    return found


# --- Data sources ----------------------------------------------------------
def _source_from_member(node: Node, source: bytes, file: str) -> Surface | None:
    """Report a data source read as a property rather than a call, e.g. process.env.KEY."""
    if node.type != "member_expression":
        return None
    text = node_text(node, source)
    for prefix, detail in DATA_SOURCE_MEMBERS.items():
        if text.startswith(prefix + "."):
            return _surface(DATA_SOURCE, text, file, node, detail, "")
    return None


def find_data_sources(tree: Node, file: str, source: bytes) -> list[Surface]:
    """Find the sites where outside data enters: files, requests, retrieval.

    Phase 1 records source sites only. Tracing whether they reach a prompt or a
    tool is Phase 3's taint probe, deliberately not done here.
    """
    imports = build_import_table(tree, source)
    found = []
    for node in walk(tree):
        member = _source_from_member(node, source, file)
        if member is not None:
            found.append(member)
            continue
        if node.type not in CALL_NODES:
            continue
        name = call_name(node, source)
        detail = DATA_SOURCE_CALLS.get(name) or DATA_SOURCE_METHODS.get(name.split(".")[-1])
        if detail is None:
            continue
        found.append(_surface(DATA_SOURCE, name, file, node, detail,
                              imports.get(call_root(node, source), "")))
    return found


def _surface(kind: str, name: str, file: str, node: Node, detail: str, module: str) -> Surface:
    """Build one Surface from a tree-sitter node, keeping the language correct."""
    return Surface(kind, name, file, line_of(node), language_of(file),
                   detail=detail, module=module)
