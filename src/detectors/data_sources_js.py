"""Finds where outside data enters a JavaScript or TypeScript app.

Split out of `detectors_js.py`: this is the detector that keeps growing, so it
gets its own file and leaves the prompt, agent and tool detectors alone.
"""

from tree_sitter import Node

from detectors.detector_names_js import (
    DATA_SOURCE_CALLS,
    DATA_SOURCE_MEMBERS,
    DATA_SOURCE_METHODS,
    ROUTE_METHODS,
    ROUTE_OBJECTS,
    ROUTE_PATH_PREFIX,
)
from detectors.surface_builder_js import surface_from_node
from artifacts.surface import DATA_SOURCE, Surface
from parsing.ts_utils import (
    CALL_NODES,
    build_import_table,
    call_name,
    call_root,
    node_text,
    string_value,
    walk,
)

MEMBER_NODE = "member_expression"

# What separates a receiver from the method called on it, as on the Python side.
RECEIVER_SEPARATOR = "."


def _method_detail(name: str) -> str | None:
    """Describe a method match, but only when the receiver can be named.

    `load`, `query` and `execute` match any object at all, so a call whose
    receiver the tree cannot name -- `resp.json().load()` -- says nothing about
    outside data being read.
    """
    receiver, separator, method = name.rpartition(RECEIVER_SEPARATOR)
    if not separator or not receiver:
        return None
    return DATA_SOURCE_METHODS.get(method)

# A route path is written as a plain or template literal.
PATH_NODES = ("string", "template_string")

# A registration needs a path *and* a handler, so `app.use('/api')` alone
# mounts nothing and is not an entry point. This is the only thing the count
# guards: `app.get('port')` is already rejected for having no leading slash,
# and `app.use(express.json())` for its first argument not being a literal.
# `route` is the exception -- `app.route('/x')` takes the path alone, and the
# handler is chained onto what it returns.
ROUTE_MIN_ARGUMENTS = 2
PATH_ONLY_METHOD = "route"


def _source_from_member(node: Node, source: bytes, file: str) -> Surface | None:
    """Report a data source read as a property rather than a call, e.g. process.env.KEY."""
    if node.type != MEMBER_NODE:
        return None
    text = node_text(node, source)
    for prefix, detail in DATA_SOURCE_MEMBERS.items():
        if text.startswith(prefix + "."):
            return surface_from_node(DATA_SOURCE, text, file, node, detail, "")
    return None


def _route_detail(method: str) -> str:
    """Describe a route registration the way the Python side describes its decorator."""
    return "http route input" if method == "route" else f"http {method} route input"


def _source_from_route(node: Node, source: bytes, file: str) -> Surface | None:
    """Report an Express-style route registration: where request data enters the app."""
    if node.type not in CALL_NODES:
        return None
    name = call_name(node, source)
    obj, _, method = name.rpartition(".")
    if obj not in ROUTE_OBJECTS or method not in ROUTE_METHODS:
        return None
    arguments = node.child_by_field_name("arguments")
    given = list(arguments.named_children) if arguments is not None else []
    wanted = 1 if method == PATH_ONLY_METHOD else ROUTE_MIN_ARGUMENTS
    if len(given) < wanted or given[0].type not in PATH_NODES:
        return None
    if not string_value(given[0], source).startswith(ROUTE_PATH_PREFIX):
        return None
    # No module: `app` is a local bound to `express()`, so naming the package
    # it came from needs dataflow, which is Phase 3's job.
    return surface_from_node(DATA_SOURCE, name, file, node, _route_detail(method), "")


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
        route = _source_from_route(node, source, file)
        if route is not None:
            found.append(route)
            continue
        if node.type not in CALL_NODES:
            continue
        name = call_name(node, source)
        detail = DATA_SOURCE_CALLS.get(name)
        if detail is None:
            detail = _method_detail(name)
        if detail is None:
            continue
        found.append(surface_from_node(DATA_SOURCE, name, file, node, detail,
                                       imports.get(call_root(node, source), "")))
    return found
