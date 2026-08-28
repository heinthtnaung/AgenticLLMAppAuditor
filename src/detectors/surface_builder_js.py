"""Builds a Surface from a tree-sitter node.

Detector glue, kept out of `parsing/ts_utils.py` on purpose: that module's job
is reading a syntax tree and it knows nothing about surfaces. Public rather
than private because two detector modules import it.
"""

from tree_sitter import Node

from artifacts.surface import Surface
from parsing.languages import language_of
from parsing.ts_utils import line_of


def surface_from_node(kind: str, name: str, file: str, node: Node,
                      detail: str, module: str) -> Surface:
    """Build one Surface from a tree-sitter node, keeping the language correct."""
    return Surface(kind, name, file, line_of(node), language_of(file),
                   detail=detail, module=module)
