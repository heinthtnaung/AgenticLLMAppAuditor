"""The two spellings of an MCP client the AIBOM still files as an ordinary TOOL, as strict xfails.

`_kind_of` decides between `MCP_SERVER` and `TOOL` with
`surface.name.split(".")[0] in MCP_CLASSES` -- it asks whether the *surface's
name* is an MCP class. But the tool detectors do not name a surface after the
class they matched. `_tool_from_call` names it `keyword_string(node, "name") or
call_name(node)`, so `MCPToolkit(name="orders")` yields a surface called
`orders`; `_tool_from_class` names it `node.name`, so a class subclassing
`ClientSession` yields a surface called after the subclass. Neither string is in
`MCP_CLASSES`, so both are filed as `TOOL`. Measured on the app written below:

    MCPToolkit(name="orders")           surface "orders"          kind TOOL
    class OrdersSession(ClientSession)  surface "OrdersSession"    kind TOOL
    MCPToolkit(client=None)             surface "MCPToolkit"       kind MCP_SERVER

**This is the same shape-versus-membership gap `test_dataset_loader_shapes.py`
closed for DATASET**, arrived at from the other side: there a table matched the
call shape and missed an alias, here the kind test matches a name the detector
was free to replace. The import guard in `aibom.py` cannot see either, because
it asks whether the *names* in `MCP_CLASSES` are ones some detector could match
-- and `MCPToolkit` is, in exactly one of its three spellings.

**What it costs, stated so it is not overstated.** Nothing but `aibom.json`:
no check reads an AIBOM kind, so no finding and no score moves. What moves is
the bill of materials a reader is handed -- an MCP server, the process an agent
reaches for tools it did not define, listed as a tool of the app's own, and the
`MCP_SERVER` count lower than the app's true one with nothing saying so.

**Not fixed here, and not fixed by widening the table.** Adding `orders` to
`MCP_CLASSES` is absurd, and reading `detail` instead is barred: `aibom.py`
says the kind is decided against the detectors' name tables and never by
reading `detail`, which is documented as descriptive only. The fix is for the
surface to carry the class it matched -- a `Surface` field or a kind decided at
detection -- which is a change to the extractor's contract and its own task.

Both tests below are `xfail(strict=True)`: they state what the kind means, and
they will fail the moment the code starts meeting it, which is what retires
this file.
"""

import pytest

from artifacts.aibom import MCP_SERVER, TOOL, build_aibom
from artifacts.surface import TOOL_CALL
from parsing.extractor import extract_repo

# Named once so a reader chasing a strict-xfail failure is sent somewhere that
# explains it rather than to a bare test name.
RENAMED_SURFACE = (
    "the AIBOM decides MCP_SERVER from surface.name, which the tool detectors "
    "replace with a name= keyword or a subclass name, so an MCP client under "
    "either spelling is filed as an ordinary TOOL")

# Three MCP clients, one per spelling. The third takes no `name` keyword and is
# the control: it is the only one whose surface keeps the class's own name.
APP_FILE = "mcp_client.py"
APP_SOURCE = '''from langchain_community.agent_toolkits import MCPToolkit
from mcp import ClientSession

orders = MCPToolkit(name="orders")
default = MCPToolkit(client=None)


class OrdersSession(ClientSession):
    pass
'''

NAMED_TOOLKIT_LINE = 4
UNNAMED_TOOLKIT_LINE = 5
SUBCLASS_LINE = 8
EXPECTED_SURFACE_COUNT = 3


def app_kinds(tmp_path) -> dict[int, str]:
    """Write the app, extract it, and return the AIBOM kind recorded for each line."""
    (tmp_path / APP_FILE).write_text(APP_SOURCE, encoding="utf-8")
    surfaces = extract_repo(str(tmp_path)).surfaces
    assert len(surfaces) == EXPECTED_SURFACE_COUNT, \
        "the app did not extract as written, so nothing below would prove anything"
    return {component["line"]: component["kind"]
            for component in build_aibom(surfaces)["components"]}


def test_all_three_mcp_clients_are_extracted_as_tool_surfaces(tmp_path) -> None:
    """Guard: the defect is the kind, not a missing surface, and this says which."""
    (tmp_path / APP_FILE).write_text(APP_SOURCE, encoding="utf-8")
    surfaces = extract_repo(str(tmp_path)).surfaces
    assert sorted(surface.line for surface in surfaces) == \
        [NAMED_TOOLKIT_LINE, UNNAMED_TOOLKIT_LINE, SUBCLASS_LINE]
    assert {surface.kind for surface in surfaces} == {TOOL_CALL}


def test_an_mcp_client_that_keeps_its_class_name_is_an_mcp_server(tmp_path) -> None:
    """Guard: without this the two xfails could pass by MCP_SERVER never being reachable."""
    assert app_kinds(tmp_path)[UNNAMED_TOOLKIT_LINE] == MCP_SERVER


def test_the_two_defective_spellings_are_filed_as_tools_today(tmp_path) -> None:
    """The defect as it stands, so the xfails below cannot fail for some other reason."""
    kinds = app_kinds(tmp_path)
    assert kinds[NAMED_TOOLKIT_LINE] == TOOL
    assert kinds[SUBCLASS_LINE] == TOOL


@pytest.mark.xfail(strict=True, reason=RENAMED_SURFACE)
def test_an_mcp_client_given_a_name_keyword_is_still_an_mcp_server(tmp_path) -> None:
    """It reaches an MCP server; what the app chooses to call it cannot change that."""
    assert app_kinds(tmp_path)[NAMED_TOOLKIT_LINE] == MCP_SERVER


@pytest.mark.xfail(strict=True, reason=RENAMED_SURFACE)
def test_a_class_subclassing_an_mcp_client_is_still_an_mcp_server(tmp_path) -> None:
    """Subclassing `ClientSession` is how the MCP SDK is used, and the base is what it is."""
    assert app_kinds(tmp_path)[SUBCLASS_LINE] == MCP_SERVER
