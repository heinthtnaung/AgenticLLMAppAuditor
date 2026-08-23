"""Small shared helpers for reading JavaScript and TypeScript syntax trees.

The mirror of ast_utils.py for the tree-sitter backend. Python keeps its own
helpers because the standard library's ast resolves imports properly, which a
tree-sitter query cannot do without reimplementing module semantics.
"""

from collections.abc import Iterator

from tree_sitter import Node

# tree-sitter names the callee differently for a call and a construction.
CALLEE_FIELDS = {"call_expression": "function", "new_expression": "constructor"}

CALL_NODES = tuple(CALLEE_FIELDS)

# A specifier starting with . or / points at the app's own code.
FIRST_PARTY_PREFIXES = (".", "/")


def walk(node: Node) -> Iterator[Node]:
    """Yield every node in the tree, flatly, like ast.walk does for Python."""
    pending = [node]
    while pending:
        current = pending.pop()
        yield current
        pending.extend(current.children)


def node_text(node: Node, source: bytes) -> str:
    """Return the exact source text a node covers."""
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def line_of(node: Node) -> int:
    """Return a node's 1-based line number, matching what the Python backend records."""
    return node.start_point[0] + 1


def call_name(node: Node, source: bytes) -> str:
    """Return what a call or construction invokes, e.g. 'ChatPromptTemplate.fromMessages'."""
    field = CALLEE_FIELDS.get(node.type)
    if field is None:
        return ""
    callee = node.child_by_field_name(field)
    return node_text(callee, source) if callee is not None else ""


def call_root(node: Node, source: bytes) -> str:
    """Return the leftmost name of a call, e.g. 'ChatPromptTemplate'."""
    return call_name(node, source).split(".")[0]


def string_value(node: Node, source: bytes) -> str:
    """Return a string literal's text without its surrounding quotes."""
    return node_text(node, source).strip("\"'`")


def _is_type_only(statement: Node, source: bytes) -> bool:
    """Say whether an import brings in types only, which cannot create a runtime surface."""
    return any(node_text(child, source) == "type" for child in statement.children)


def build_import_table(root: Node, source: bytes) -> dict[str, str]:
    """Map each imported name to the package specifier it came from.

    Two kinds of import are skipped. A type-only import (`import type { X }`)
    disappears at build time and can never produce a surface. A relative import
    (`./tools`) is the app's own code, not a package, so it records no module —
    the same rule the Python backend applies to `from .settings import x`.
    """
    table: dict[str, str] = {}
    for statement in walk(root):
        if statement.type != "import_statement" or _is_type_only(statement, source):
            continue
        specifier_node = statement.child_by_field_name("source")
        if specifier_node is None:
            continue
        specifier = string_value(specifier_node, source)
        if specifier.startswith(FIRST_PARTY_PREFIXES):
            continue
        for imported in walk(statement):
            _record_imported_name(imported, specifier, source, table)
    return table


def _record_imported_name(node: Node, specifier: str, source: bytes, table: dict[str, str]) -> None:
    """Record one imported name, preferring its local alias when it has one."""
    if node.type not in ("import_specifier", "namespace_import", "identifier"):
        return
    if node.type == "import_specifier":
        alias = node.child_by_field_name("alias") or node.child_by_field_name("name")
        table[node_text(alias, source)] = specifier
        return
    local = node.child_by_field_name("name") if node.type == "namespace_import" else node
    if local is not None and node.parent is not None and node.parent.type != "import_specifier":
        table.setdefault(node_text(local, source), specifier)


def declared_name(node: Node, source: bytes) -> str:
    """Return the variable a declaration binds, or '' if it has no plain name."""
    target = node.child_by_field_name("name")
    return node_text(target, source) if target is not None else ""


def text_shape(value: Node) -> str:
    """Name how an expression builds text, or '' if it does not build text at all."""
    if value.type == "template_string":
        return "template literal"
    if value.type == "string":
        return "string"
    if value.type == "binary_expression":
        return "concatenated string"
    return ""
