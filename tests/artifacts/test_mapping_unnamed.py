"""Surfaces with no import behind them, which is most of them.

`cursor.execute` and `open` cannot be traced to a package by static analysis
alone. Saying so is the honest answer; guessing a package name here is what
produces findings nobody can check.
"""

from artifacts.mapping import FIRST_PARTY, STDLIB, UNRESOLVED, build_mapping
from artifacts.surface import DATA_SOURCE, PROMPT_TEMPLATE, Surface
from dependency_fixtures import corpus_sbom
from deps.component_match import NOT_RESOLVED
from parsing.languages import JAVASCRIPT, PYTHON


def entry_for(name: str, kind: str = DATA_SOURCE, language: str = PYTHON) -> dict:
    """Map a single surface that records no module and return its one entry."""
    file = "app.py" if language == PYTHON else "app.js"
    surface = Surface(kind, name, file, 3, language, "")
    return build_mapping([surface], corpus_sbom())["entries"][0]


def test_a_dotted_name_is_unresolved() -> None:
    """`cursor.execute` is a method on an object whose type needs dataflow to know."""
    assert entry_for("cursor.execute")["reason"] == UNRESOLVED


def test_a_dotted_name_names_no_component() -> None:
    """Unresolved means unresolved: no package is guessed from the prefix."""
    entry = entry_for("cursor.execute")
    assert entry["component_name"] is None
    assert entry["resolved_by"] == NOT_RESOLVED


def test_a_plain_name_is_first_party() -> None:
    """`system_msg` is a variable the app defined, so it belongs to the app."""
    assert entry_for("system_msg", PROMPT_TEMPLATE)["reason"] == FIRST_PARTY


def test_a_builtin_is_stdlib() -> None:
    """`open` is a Python builtin, so no package ships it and none is missing."""
    assert entry_for("open")["reason"] == STDLIB


def test_a_javascript_global_is_stdlib() -> None:
    """`fetch` is part of the JS runtime; Python's builtins list knows nothing of it."""
    assert entry_for("fetch", language=JAVASCRIPT)["reason"] == STDLIB


def test_a_dotted_javascript_global_is_stdlib() -> None:
    """`console.log` is the runtime too, decided on the leading segment."""
    assert entry_for("console.log", language=JAVASCRIPT)["reason"] == STDLIB


def test_an_unnamed_surface_keeps_its_module_field_empty() -> None:
    """The entry reports the empty module rather than inventing one."""
    assert entry_for("cursor.execute")["module"] == ""


def test_no_unnamed_surface_ever_gets_a_purl() -> None:
    """Nothing was resolved, so nothing may be keyed on for an advisory lookup."""
    for name in ("cursor.execute", "system_msg", "open"):
        assert entry_for(name)["purl"] is None, name
