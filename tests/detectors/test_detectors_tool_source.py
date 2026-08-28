"""The tool and data-source detectors: what the model can reach."""

import pytest
from detector_helpers import (
    FILE,
    BOTH_ROUTES_SOURCE,
    DATA_SOURCE_SOURCE,
    ROUTE_SOURCE,
    TOOL_CONSTRUCTOR_SOURCE,
    TOOL_DECORATOR_SOURCE,
    TOOL_SUBCLASS_SOURCE,
    only,
    parse,
)
from detectors.detector_names import DATA_SOURCE_CALLS, OPEN_CALL
from detectors.detectors import find_data_sources, find_tool_calls
from artifacts.surface import DATA_SOURCE, TOOL_CALL


def test_finds_tool_decorated_function() -> None:
    """A @tool function is reported as a TOOL_CALL at the def line, not the decorator."""
    surface = only(find_tool_calls(parse(TOOL_DECORATOR_SOURCE), FILE))
    assert (surface.kind, surface.name, surface.line) == (TOOL_CALL, "lookup_user", 5)


def test_finds_tool_constructor_and_prefers_its_name_keyword() -> None:
    """A Tool(...) constructor is named by its name keyword, and keeps its import module."""
    surface = only(find_tool_calls(parse(TOOL_CONSTRUCTOR_SOURCE), FILE))
    assert (surface.kind, surface.name, surface.line) == (TOOL_CALL, "GetUserTransactions", 3)
    assert surface.module == "langchain.agents"


def test_finds_tool_subclass() -> None:
    """A class subclassing a framework tool base is reported at the class line."""
    surface = only(find_tool_calls(parse(TOOL_SUBCLASS_SOURCE), FILE))
    assert (surface.kind, surface.name, surface.line) == (TOOL_CALL, "ShellRunner", 4)


# --- Data sources ----------------------------------------------------------
def test_finds_outbound_request_as_data_source() -> None:
    """An outbound http call is reported as a DATA_SOURCE at its own line."""
    surface = only(find_data_sources(parse(DATA_SOURCE_SOURCE), FILE))
    assert (surface.kind, surface.name, surface.line) == (DATA_SOURCE, "requests.get", 3)
    assert surface.module == "requests"


def test_finds_web_route_handler_as_data_source() -> None:
    """A route handler is reported as a DATA_SOURCE because it receives request input."""
    surface = only(find_data_sources(parse(ROUTE_SOURCE), FILE))
    assert (surface.kind, surface.name, surface.line) == (DATA_SOURCE, "chat", 2)


# --- Detector independence -------------------------------------------------


def test_route_handlers_are_data_sources_with_readable_detail() -> None:
    """Both Flask @app.route and FastAPI @app.post handlers read as request inputs."""
    found = {s.name: s.detail for s in find_data_sources(parse(BOTH_ROUTES_SOURCE), "api.py")}
    assert found["flask_handler"] == "http route input"
    assert found["fastapi_handler"] == "http post route input"


RELATIVE_IMPORT_SOURCE = """
from .settings import Tool

lookup = Tool(name="GetUser", func=None)
"""


def test_relative_import_records_no_module() -> None:
    """First-party code is not a package, so a relative import must record no module."""
    surface = only(find_tool_calls(parse(RELATIVE_IMPORT_SOURCE), FILE))
    assert surface.module == ""


# --- open() ----------------------------------------------------------------
OPEN_READ_SOURCE = """
def load_notes(path):
    handle = open(path)
    return handle
"""

OPEN_WRITE_SOURCE = """
def save_notes(path):
    handle = open(path, "w")
    return handle
"""

# The same write, passed the way Python also allows: mode as a keyword.
OPEN_KEYWORD_MODE_SOURCE = """
def save_notes(path):
    handle = open(path, mode="w")
    return handle
"""

# Binary reading: a mode with no write flag in it at all.
OPEN_BINARY_READ_SOURCE = """
def load_notes(path):
    handle = open(path, "rb")
    return handle
"""

# `+` opens for update, so this handle writes as well as reads. It was reported
# as a plain read until `+` joined the write flags.
OPEN_UPDATE_SOURCE = """
def load_notes(path):
    handle = open(path, "r+")
    return handle
"""

# The same update in binary: `+` is the flag that matters, wherever it sits.
OPEN_BINARY_UPDATE_SOURCE = """
def load_notes(path):
    handle = open(path, "rb+")
    return handle
"""

# A mode the source does not spell out, so no mode can be read from it.
OPEN_RUNTIME_MODE_SOURCE = """
def load_notes(path, mode_from_config):
    handle = open(path, mode_from_config)
    return handle
"""


def test_open_is_not_in_the_data_source_call_table() -> None:
    """The detector branches on OPEN_CALL first, so a table entry would be a second definition."""
    assert OPEN_CALL not in DATA_SOURCE_CALLS


@pytest.mark.parametrize("source, expected_detail", [
    (OPEN_READ_SOURCE, "file read"),
    (OPEN_BINARY_READ_SOURCE, "file read"),
    (OPEN_WRITE_SOURCE, "file write"),
    (OPEN_KEYWORD_MODE_SOURCE, "file write"),
    (OPEN_UPDATE_SOURCE, "file write"),
    (OPEN_BINARY_UPDATE_SOURCE, "file write"),
], ids=["no mode", "rb", "w", "keyword w", "r+", "rb+"])
def test_open_detail_is_computed_from_its_mode(source: str, expected_detail: str) -> None:
    """open() is a DATA_SOURCE whose detail comes from its mode, positional or keyword.

    `r+` and `rb+` are the cases the mode table used to get wrong: both open a
    read-write handle, and both read as `file read` until `+` counted as a write.
    """
    surface = only(find_data_sources(parse(source), FILE))
    assert (surface.kind, surface.name, surface.line) == (DATA_SOURCE, OPEN_CALL, 2)
    assert surface.detail == expected_detail


def test_open_with_a_runtime_mode_says_so() -> None:
    """A mode that is not a literal is reported as undecided, never guessed at as a read."""
    surface = only(find_data_sources(parse(OPEN_RUNTIME_MODE_SOURCE), FILE))
    assert (surface.kind, surface.name, surface.line) == (DATA_SOURCE, OPEN_CALL, 2)
    assert surface.detail == "file access, mode decided at runtime"
