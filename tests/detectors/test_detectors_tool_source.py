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
