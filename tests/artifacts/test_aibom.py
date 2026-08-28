"""The AI parts of the corpus app: its model client, its agents and its tools.

Every entry is derived from an extracted surface and carries that surface's id,
so a reader can go back to the line it came from. An entry nobody can trace is
an entry nobody can check.
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
from dependency_fixtures import corpus_surfaces
from parsing.languages import PYTHON

# Measured on corpus/vuln-app-1-support-agent: kind, name, file, line.
EXPECTED_COMPONENTS = [
    (MODEL, "ChatLiteLLM", "main.py", 63),
    (AGENT, "ConversationalChatAgent.from_llm_and_tools", "main.py", 69),
    (AGENT, "AgentExecutor.from_agent_and_tools", "main.py", 71),
    (TOOL, "GetCurrentUser", "tools.py", 22),
    (TOOL, "GetUserTransactions", "tools.py", 40),
]


def corpus_aibom() -> dict:
    """Build the corpus app's AIBOM from its extracted surfaces."""
    return build_aibom(corpus_surfaces())


def identities(document: dict) -> set[tuple[str, str, str, int]]:
    """Reduce an AIBOM to the (kind, name, file, line) of each component."""
    return {(c["kind"], c["name"], c["file"], c["line"]) for c in document["components"]}


def test_the_corpus_app_yields_exactly_the_five_expected_components() -> None:
    """One model client, two agents and two tools, at the lines they are written on."""
    assert identities(corpus_aibom()) == set(EXPECTED_COMPONENTS)


def test_the_component_count_matches_the_component_list() -> None:
    """A count that disagrees with the list makes every summary wrong."""
    document = corpus_aibom()
    assert document["component_count"] == len(document["components"]) == 5


def test_every_component_traces_back_to_an_extracted_surface() -> None:
    """A component whose surface id does not exist could not be checked by a reader."""
    surface_ids = {surface.id for surface in corpus_surfaces()}
    for component in corpus_aibom()["components"]:
        assert component["surface_id"] in surface_ids, component


def test_the_model_client_is_the_only_model() -> None:
    """ChatLiteLLM is a model client; the two agent constructors are not."""
    models = [c["name"] for c in corpus_aibom()["components"] if c["kind"] == MODEL]
    assert models == ["ChatLiteLLM"]


def test_the_agent_constructors_are_agents_not_models() -> None:
    """An AgentExecutor wires tools to a model; calling it a model loses that distinction."""
    agents = {c["name"] for c in corpus_aibom()["components"] if c["kind"] == AGENT}
    assert agents == {"ConversationalChatAgent.from_llm_and_tools",
                      "AgentExecutor.from_agent_and_tools"}


def test_the_two_planted_tools_are_listed() -> None:
    """Both tools the demo app exposes to the agent appear, with their files."""
    tools = {(c["name"], c["file"]) for c in corpus_aibom()["components"]
             if c["kind"] == TOOL}
    assert tools == {("GetCurrentUser", "tools.py"), ("GetUserTransactions", "tools.py")}


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


def test_a_model_records_that_its_model_name_is_unstated() -> None:
    """No surface records which model is called, so the AIBOM says so rather than guessing."""
    model = next(c for c in corpus_aibom()["components"] if c["kind"] == MODEL)
    assert model["model_source"] == UNSTATED


def test_a_tool_records_that_a_model_name_does_not_apply() -> None:
    """A tool has no model, which is different from having an unknown one."""
    tool = next(c for c in corpus_aibom()["components"] if c["kind"] == TOOL)
    assert tool["model_source"] == NOT_APPLICABLE


def test_a_prompt_template_is_not_an_aibom_component() -> None:
    """Prompts are surfaces, not AI components; including them would double-count."""
    surface = Surface(PROMPT_TEMPLATE, "system_msg", "main.py", 21, PYTHON, "")
    assert build_aibom([surface])["components"] == []


def test_components_are_ordered_by_kind_then_location() -> None:
    """A fixed order is what lets two runs of aibom.json be compared."""
    keys = [(c["kind"], c["file"], c["line"], c["name"])
            for c in corpus_aibom()["components"]]
    assert keys == sorted(keys)


def test_an_app_with_no_ai_components_yields_an_empty_aibom() -> None:
    """Zero components is an answer, not an error."""
    document = build_aibom([])
    assert document["component_count"] == 0
    assert document["components"] == []
