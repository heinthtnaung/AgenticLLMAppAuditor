"""The two AI component kinds the AIBOM gained: DATASET and MCP_SERVER.

The proposal names datasets and MCP servers among the AI components a bill of
materials should record, and neither was there: a dataset loader was only a
data source and an MCP client only a tool. Both are now lifted, and both are
decided by a *name table the detectors own* -- so this file is about the two
boundaries that lifting draws.

**Kept apart from `test_aibom.py` on purpose.** That file's pinned
five-component list describes a different app and must stay what it was
measured as; this one writes its own app.

**The app is written here and really extracted**, so the file names and lines
below are the author's own. What that costs is the usual: no oversized file, no
framework idiom its author did not think of, and only Python -- neither new
kind is reachable from the JavaScript backend today, because the tables
`_kind_of` reads are `detector_names.py`'s.
"""

from artifacts.aibom import (
    AGENT,
    AIBOM_KINDS,
    DATASET,
    MCP_SERVER,
    MODEL,
    NOT_APPLICABLE,
    TOOL,
    UNSTATED,
    build_aibom,
)
from artifacts.surface import DATA_SOURCE, TOOL_CALL
from parsing.extractor import extract_repo

# The written app. `cursor.execute` on the last line is the boundary that
# matters: it is a data source and it is not a dataset, so it must produce no
# component at all. `MCPToolkit.from_client` is the other one: the MCP test is
# on the call *root*, so a factory call on an MCP class is still an MCP server.
CORPUS_FILE = "corpus.py"
CORPUS_SOURCE = '''import datasets
from datasets import load_dataset
from langchain_openai import ChatOpenAI

examples = load_dataset("squad")
cached = datasets.load_from_disk("./cache")
llm = ChatOpenAI()


def recent_tickets(cursor, user):
    return cursor.execute("SELECT * FROM tickets WHERE user = ?", (user,))
'''

MCP_FILE = "mcp_client.py"
MCP_SOURCE = '''from langchain_community.agent_toolkits import MCPToolkit
from langchain_community.tools import Tool
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({})
toolkit = MCPToolkit.from_client(client)
lookup = Tool(name="lookup_order", func=None)
'''

# Read off the source above: kind, name, file, line. Six components from seven
# surfaces -- `cursor.execute` is the seventh and is deliberately absent.
EXPECTED_COMPONENTS = {
    (DATASET, "load_dataset", CORPUS_FILE, 5),
    (DATASET, "datasets.load_from_disk", CORPUS_FILE, 6),
    (MODEL, "ChatOpenAI", CORPUS_FILE, 7),
    (MCP_SERVER, "MultiServerMCPClient", MCP_FILE, 5),
    (MCP_SERVER, "MCPToolkit.from_client", MCP_FILE, 6),
    (TOOL, "lookup_order", MCP_FILE, 7),
}
EXPECTED_SURFACE_COUNT = 7
QUERY_SURFACE_NAME = "cursor.execute"


def app_surfaces(tmp_path) -> list:
    """Write the app and extract its surfaces, the way an audit would."""
    (tmp_path / CORPUS_FILE).write_text(CORPUS_SOURCE, encoding="utf-8")
    (tmp_path / MCP_FILE).write_text(MCP_SOURCE, encoding="utf-8")
    surfaces = extract_repo(str(tmp_path)).surfaces
    assert len(surfaces) == EXPECTED_SURFACE_COUNT, \
        "the app did not extract as written, so the AIBOM below would prove nothing"
    return surfaces


def app_aibom(tmp_path) -> dict:
    """Build the written app's AIBOM from its extracted surfaces."""
    return build_aibom(app_surfaces(tmp_path))


def identities(document: dict) -> set[tuple[str, str, str, int]]:
    """Reduce an AIBOM to the (kind, name, file, line) of each component."""
    return {(c["kind"], c["name"], c["file"], c["line"]) for c in document["components"]}


def names_of_kind(document: dict, kind: str) -> set[str]:
    """The names of every component the AIBOM filed under one kind."""
    return {c["name"] for c in document["components"] if c["kind"] == kind}


# --- The whole app ----------------------------------------------------------

def test_the_written_app_yields_exactly_the_six_expected_components(tmp_path) -> None:
    """Two datasets, two MCP servers, one model and one tool, at the lines they sit on."""
    assert identities(app_aibom(tmp_path)) == EXPECTED_COMPONENTS


def test_the_component_count_matches_the_component_list(tmp_path) -> None:
    """A count that disagrees with the list makes every summary of the file wrong."""
    document = app_aibom(tmp_path)
    assert document["component_count"] == len(document["components"]) == len(EXPECTED_COMPONENTS)


def test_the_five_kinds_still_sort_into_a_fixed_order(tmp_path) -> None:
    """Two new kinds must not disturb the order that lets two runs be compared."""
    keys = [(c["kind"], c["file"], c["line"], c["name"])
            for c in app_aibom(tmp_path)["components"]]
    assert keys == sorted(keys)


# --- DATASET: a loader, not every data source -------------------------------

def test_a_dataset_loaded_by_name_is_a_dataset_component(tmp_path) -> None:
    """`load_dataset("squad")` pulls in a named corpus whole, which is an AI component."""
    assert "load_dataset" in names_of_kind(app_aibom(tmp_path), DATASET)


def test_a_dataset_loaded_from_disk_is_matched_on_the_name_leaf(tmp_path) -> None:
    """`datasets.load_from_disk(...)` is dotted, so the last segment is what is tested."""
    assert "datasets.load_from_disk" in names_of_kind(app_aibom(tmp_path), DATASET)


def test_a_database_query_is_a_data_source_and_not_a_dataset(tmp_path) -> None:
    """The boundary the kind rests on: `cursor.execute` reads data the app already holds.

    Calling every data source a dataset would file every SQL query, every
    `os.getenv` and every HTTP fetch in the bill of materials as a corpus,
    which is not what a reader of an AIBOM is being told.
    """
    surfaces = app_surfaces(tmp_path)
    query = [s for s in surfaces if s.name == QUERY_SURFACE_NAME]
    assert len(query) == 1 and query[0].kind == DATA_SOURCE
    assert QUERY_SURFACE_NAME not in {c["name"] for c in build_aibom(surfaces)["components"]}


def test_a_data_source_that_is_no_dataset_produces_no_component_at_all(tmp_path) -> None:
    """Not a component of another kind either: it is left out, as prompts are."""
    surfaces = [s for s in app_surfaces(tmp_path) if s.name == QUERY_SURFACE_NAME]
    assert build_aibom(surfaces)["components"] == []


def test_a_dataset_records_that_a_model_name_does_not_apply(tmp_path) -> None:
    """A corpus has no model, which is different from having an unknown one."""
    dataset = next(c for c in app_aibom(tmp_path)["components"] if c["kind"] == DATASET)
    assert dataset["model_source"] == NOT_APPLICABLE


# --- MCP_SERVER: an MCP client, not every tool ------------------------------

def test_an_mcp_client_is_an_mcp_server_component(tmp_path) -> None:
    """`MultiServerMCPClient({...})` reaches a server for tools the app does not define."""
    assert "MultiServerMCPClient" in names_of_kind(app_aibom(tmp_path), MCP_SERVER)


def test_an_mcp_class_factory_call_is_matched_on_the_name_root(tmp_path) -> None:
    """`MCPToolkit.from_client(...)` extracts dotted, so the *first* segment is tested.

    Testing the whole name instead would file this one as an ordinary tool,
    and the surface really is named that way -- the detector matches the call
    root and then names the surface with the chain it found.
    """
    assert "MCPToolkit.from_client" in names_of_kind(app_aibom(tmp_path), MCP_SERVER)


def test_an_ordinary_tool_stays_a_tool(tmp_path) -> None:
    """The boundary in the other direction: a tool the app wrote is not an MCP server."""
    assert names_of_kind(app_aibom(tmp_path), TOOL) == {"lookup_order"}


def test_a_tool_call_surface_is_one_kind_or_the_other_and_never_dropped(tmp_path) -> None:
    """Splitting TOOL_CALL in two must not lose one: every tool surface still appears."""
    tools = [s for s in app_surfaces(tmp_path) if s.kind == TOOL_CALL]
    document = app_aibom(tmp_path)
    listed = names_of_kind(document, TOOL) | names_of_kind(document, MCP_SERVER)
    assert listed == {surface.name for surface in tools}


def test_an_mcp_server_records_that_a_model_name_does_not_apply(tmp_path) -> None:
    """An MCP server serves tools; it is not a model client with an unknown model."""
    server = next(c for c in app_aibom(tmp_path)["components"] if c["kind"] == MCP_SERVER)
    assert server["model_source"] == NOT_APPLICABLE


# --- The kinds themselves ---------------------------------------------------

def test_the_aibom_holds_exactly_five_kinds() -> None:
    """A reader of `aibom.json` needs the whole list, and it is five now, not three."""
    assert AIBOM_KINDS == (MODEL, TOOL, AGENT, DATASET, MCP_SERVER)
    assert len(set(AIBOM_KINDS)) == len(AIBOM_KINDS)


def test_every_component_the_written_app_yields_carries_a_known_kind(tmp_path) -> None:
    """A kind outside the list would be a value no reader of the artifact expects."""
    for component in app_aibom(tmp_path)["components"]:
        assert component["kind"] in AIBOM_KINDS, component


def test_the_model_is_still_the_only_unstated_model_source(tmp_path) -> None:
    """Two new kinds must not start claiming a model whose name is merely unknown."""
    unstated = {c["name"] for c in app_aibom(tmp_path)["components"]
                if c["model_source"] == UNSTATED}
    assert unstated == {"ChatOpenAI"}
