"""Guards that both risk renderings take their shared flags from one place."""

import ast
from pathlib import Path

from report import html_risk, risk_words, text_risk

SHARED_FLAGS = (risk_words.PROVISIONAL, risk_words.FLOORED_BY)


def test_the_flags_read_as_english():
    assert risk_words.PROVISIONAL == "provisional"
    assert risk_words.FLOORED_BY == "floored by"


def restated_flags(module) -> list[str]:
    """Name every shared flag a module writes as its own literal instead of importing it."""
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    literals = (node.value for node in ast.walk(tree) if isinstance(node, ast.Constant))
    return [value for value in literals if value in SHARED_FLAGS]


def test_the_terminal_rendering_restates_no_shared_flag():
    # An `is` check cannot see this: CPython interns "provisional", so a restated
    # literal keeps passing identity. The words must be imported, never re-typed.
    assert restated_flags(text_risk) == []


def test_the_web_rendering_restates_no_shared_flag():
    assert restated_flags(html_risk) == []
