"""The AI parts of an app: its model client, its agents and its tools.

Every entry is derived from an extracted surface and carries that surface's id,
so a reader can go back to the line it came from. An entry nobody can trace is
an entry nobody can check.

**The app is written by this test** and then really extracted, since the pinned
one these counts were measured on was removed -- so the file names and line
numbers below are the author's own, and no framework idiom appears that its
author did not think of. What is preserved is the path: source on disk, through
the extractor, into the AIBOM, with the kinds and lines asserted as literals.
"""

from artifacts.aibom import (
    AGENT,
    MODEL,
    NOT_APPLICABLE,
    TOOL,
    UNSTATED,
    build_aibom,
)
from artifacts.surface import AGENT_DEF, PROMPT_TEMPLATE, Surface
from parsing.extractor import extract_repo
from parsing.languages import PYTHON

# The written app: one model client and two agent constructors in one file,
# two tools in another, so file and kind both vary across the components.
MAIN_FILE = "main.py"
MAIN_SOURCE = '''from langchain.agents import AgentExecutor, ConversationalChatAgent
from langchain_litellm import ChatLiteLLM

llm = ChatLiteLLM(model="gpt-4o-mini")
chat_agent = ConversationalChatAgent.from_llm_and_tools(llm=llm, tools=[])
executor = AgentExecutor.from_agent_and_tools(agent=chat_agent, tools=[])
'''

TOOLS_FILE = "tools.py"
TOOLS_SOURCE = '''from langchain.tools import Tool

current_user = Tool(name="GetCurrentUser", func=None)
transactions = Tool(name="GetUserTransactions", func=None)
'''

# Read off the source above: kind, name, file, line.
EXPECTED_COMPONENTS = [
    (MODEL, "ChatLiteLLM", MAIN_FILE, 4),
    (AGENT, "ConversationalChatAgent.from_llm_and_tools", MAIN_FILE, 5),
    (AGENT, "AgentExecutor.from_agent_and_tools", MAIN_FILE, 6),
    (TOOL, "GetCurrentUser", TOOLS_FILE, 3),
    (TOOL, "GetUserTransactions", TOOLS_FILE, 4),
]


def app_surfaces(tmp_path) -> list:
    """Write the app and extract its surfaces, the way an audit would."""
    (tmp_path / MAIN_FILE).write_text(MAIN_SOURCE, encoding="utf-8")
    (tmp_path / TOOLS_FILE).write_text(TOOLS_SOURCE, encoding="utf-8")
    surfaces = extract_repo(str(tmp_path)).surfaces
    assert surfaces, "the app yielded no surfaces, so an empty AIBOM would prove nothing"
    return surfaces


def app_aibom(tmp_path) -> dict:
    """Build the written app's AIBOM from its extracted surfaces."""
    return build_aibom(app_surfaces(tmp_path))


def identities(document: dict) -> set[tuple[str, str, str, int]]:
    """Reduce an AIBOM to the (kind, name, file, line) of each component."""
    return {(c["kind"], c["name"], c["file"], c["line"]) for c in document["components"]}


def test_the_written_app_yields_exactly_the_five_expected_components(tmp_path) -> None:
    """One model client, two agents and two tools, at the lines they are written on."""
    assert identities(app_aibom(tmp_path)) == set(EXPECTED_COMPONENTS)


def test_the_component_count_matches_the_component_list(tmp_path) -> None:
    """A count that disagrees with the list makes every summary wrong."""
    document = app_aibom(tmp_path)
    assert document["component_count"] == len(document["components"]) == len(EXPECTED_COMPONENTS)


def test_every_component_traces_back_to_an_extracted_surface(tmp_path) -> None:
    """A component whose surface id does not exist could not be checked by a reader."""
    surface_ids = {surface.id for surface in app_surfaces(tmp_path)}
    for component in app_aibom(tmp_path)["components"]:
        assert component["surface_id"] in surface_ids, component


def test_the_model_client_is_the_only_model(tmp_path) -> None:
    """ChatLiteLLM is a model client; the two agent constructors are not."""
    models = [c["name"] for c in app_aibom(tmp_path)["components"] if c["kind"] == MODEL]
    assert models == ["ChatLiteLLM"]


def test_the_agent_constructors_are_agents_not_models(tmp_path) -> None:
    """An AgentExecutor wires tools to a model; calling it a model loses that distinction."""
    agents = {c["name"] for c in app_aibom(tmp_path)["components"] if c["kind"] == AGENT}
    assert agents == {"ConversationalChatAgent.from_llm_and_tools",
                      "AgentExecutor.from_agent_and_tools"}


def test_both_tools_are_listed(tmp_path) -> None:
    """Both tools the app exposes to the agent appear, with their files."""
    tools = {(c["name"], c["file"]) for c in app_aibom(tmp_path)["components"]
             if c["kind"] == TOOL}
    assert tools == {("GetCurrentUser", TOOLS_FILE), ("GetUserTransactions", TOOLS_FILE)}


def test_a_model_client_stays_a_model_when_its_detail_says_otherwise() -> None:
    """`detail` is descriptive only, so rewording it must not change the kind.

    Deciding on `detail` is what made a reworded detector message silently move
    a model client into the agent list.
    """
    surface = Surface(AGENT_DEF, "ChatLiteLLM", "main.py", 63, PYTHON,
                      "agent executor built from tools")
    assert build_aibom([surface])["components"][0]["kind"] == MODEL


def test_an_agent_stays_an_agent_when_its_detail_says_model() -> None:
    """The other direction: a misleading detail must not promote an agent to a model."""
    surface = Surface(AGENT_DEF, "AgentExecutor.from_agent_and_tools", "main.py", 71,
                      PYTHON, "chat model client created")
    assert build_aibom([surface])["components"][0]["kind"] == AGENT


def test_a_model_records_that_its_model_name_is_unstated(tmp_path) -> None:
    """No surface records which model is called, so the AIBOM says so rather than guessing."""
    model = next(c for c in app_aibom(tmp_path)["components"] if c["kind"] == MODEL)
    assert model["model_source"] == UNSTATED


def test_a_tool_records_that_a_model_name_does_not_apply(tmp_path) -> None:
    """A tool has no model, which is different from having an unknown one."""
    tool = next(c for c in app_aibom(tmp_path)["components"] if c["kind"] == TOOL)
    assert tool["model_source"] == NOT_APPLICABLE


def test_a_prompt_template_is_not_an_aibom_component() -> None:
    """Prompts are surfaces, not AI components; including them would double-count."""
    surface = Surface(PROMPT_TEMPLATE, "system_msg", "main.py", 21, PYTHON, "")
    assert build_aibom([surface])["components"] == []


def test_components_are_ordered_by_kind_then_location(tmp_path) -> None:
    """A fixed order is what lets two runs of aibom.json be compared."""
    keys = [(c["kind"], c["file"], c["line"], c["name"])
            for c in app_aibom(tmp_path)["components"]]
    assert keys == sorted(keys)


def test_an_app_with_no_ai_components_yields_an_empty_aibom() -> None:
    """Zero components is an answer, not an error."""
    document = build_aibom([])
    assert document["component_count"] == 0
    assert document["components"] == []


# --- A model built by the factory function, not by a class ------------------
# A second one-file app, kept apart from the five-component one above so that
# app's pinned list stays what it was measured as. `init_chat_model` is a
# MODEL_CLASSES name, and `aibom.py` reads that same table -- so the table
# decides this artifact's contents as well as surfaces.json's, and a name added
# there changes two artifacts rather than one.
LOADER_FILE = "loader.py"
LOADER_SOURCE = '''from langchain.chat_models import init_chat_model

model = init_chat_model("openai:gpt-4")
'''
LOADER_NAME = "init_chat_model"
LOADER_LINE = 3


def loader_aibom(tmp_path) -> dict:
    """Write the one-file loader app, extract it and build its AIBOM, as an audit would."""
    (tmp_path / LOADER_FILE).write_text(LOADER_SOURCE, encoding="utf-8")
    surfaces = extract_repo(str(tmp_path)).surfaces
    assert surfaces, "the loader app yielded no surfaces, so an empty AIBOM would prove nothing"
    return build_aibom(surfaces)


def test_a_model_built_by_the_factory_function_is_a_model_component(tmp_path) -> None:
    """`init_chat_model(...)` builds a model client, so the AIBOM lists it as MODEL."""
    assert identities(loader_aibom(tmp_path)) == {
        (MODEL, LOADER_NAME, LOADER_FILE, LOADER_LINE)}


def test_the_factory_built_model_leaves_its_model_name_unstated(tmp_path) -> None:
    """The call names a model in its argument, but no surface records it, so nor may the AIBOM."""
    component = loader_aibom(tmp_path)["components"][0]
    assert component["model_source"] == UNSTATED
