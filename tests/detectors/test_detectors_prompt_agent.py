"""The prompt and agent detectors: what the application tells the model."""

from detector_helpers import (
    FILE,
    AGENT_SOURCE,
    NON_TEXT_PROMPT_SOURCE,
    PROMPT_CALL_SOURCE,
    PROMPT_CONCAT_SOURCE,
    PROMPT_FORMAT_SOURCE,
    PROMPT_STRING_SOURCE,
    only,
    parse_snippet,
)
from detectors.detector_names import MODEL_CLASSES
from detectors.detectors import find_agent_defs, find_prompt_templates
from artifacts.surface import AGENT_DEF, PROMPT_TEMPLATE


def test_finds_prompt_template_constructor() -> None:
    """A framework prompt class is reported as a PROMPT_TEMPLATE at its own line."""
    surface = only(find_prompt_templates(parse_snippet(PROMPT_CALL_SOURCE), FILE))
    assert (surface.kind, surface.name, surface.line) == (
        PROMPT_TEMPLATE,
        "ChatPromptTemplate.from_messages",
        3,
    )


def test_prompt_template_module_comes_from_the_import() -> None:
    """The prompt surface records the module the prompt class was imported from."""
    surface = only(find_prompt_templates(parse_snippet(PROMPT_CALL_SOURCE), FILE))
    assert surface.module == "langchain.prompts"


def test_finds_prompt_shaped_string_assignment() -> None:
    """A string assigned to a prompt-shaped name is reported at its real line."""
    surface = only(find_prompt_templates(parse_snippet(PROMPT_STRING_SOURCE), FILE))
    assert (surface.kind, surface.name, surface.line) == (PROMPT_TEMPLATE, "system_prompt", 3)


def test_ignores_plain_string_assignment() -> None:
    """A string with no prompt-shaped name is not a prompt surface."""
    assert find_prompt_templates(parse_snippet("greeting = \"hello\"\n"), FILE) == []


# --- Agent definitions -----------------------------------------------------
def test_finds_agent_factory_call() -> None:
    """An agent factory call is reported as an AGENT_DEF at its own line."""
    surface = only(find_agent_defs(parse_snippet(AGENT_SOURCE), FILE))
    assert (surface.kind, surface.name, surface.line) == (AGENT_DEF, "create_react_agent", 3)


def test_agent_module_comes_from_the_import() -> None:
    """The agent surface records the module the factory was imported from."""
    surface = only(find_agent_defs(parse_snippet(AGENT_SOURCE), FILE))
    assert surface.module == "langchain.agents"


# --- Tool definitions ------------------------------------------------------


def test_prompt_built_by_format_is_found() -> None:
    """A prompt assembled with .format() is a prompt surface, not just a literal."""
    found = find_prompt_templates(parse_snippet(PROMPT_FORMAT_SOURCE), "app.py")
    assembled = [s for s in found if s.name == "prompt"]
    assert len(assembled) == 1
    assert assembled[0].line == 3
    assert "formatted string" in assembled[0].detail


def test_prompt_built_by_concatenation_is_found() -> None:
    """A prompt assembled by joining strings is a prompt surface."""
    found = find_prompt_templates(parse_snippet(PROMPT_CONCAT_SOURCE), "app.py")
    assert [s.name for s in found] == ["system_prompt"]
    assert "concatenated string" in found[0].detail


def test_prompt_named_non_text_is_ignored() -> None:
    """A prompt-shaped name holding numbers or lists is not a prompt surface."""
    assert find_prompt_templates(parse_snippet(NON_TEXT_PROMPT_SOURCE), "app.py") == []


# --- Model loaders: the factory function beside the model classes -----------
# `init_chat_model` builds a model client exactly as `ChatOpenAI(...)` does, so
# it is matched on the call root like every other MODEL_CLASSES name. It was a
# recorded miss in docs/TODO.md: an app calling it had an agent surface the
# extractor never saw, and a surface nothing extracts is a surface no check
# can reach.
INIT_CHAT_MODEL_SOURCE = """
from langchain.chat_models import init_chat_model

model = init_chat_model("openai:gpt-4")
"""


def test_init_chat_model_is_registered_as_a_model_class() -> None:
    """Cheap guard on the table itself: a merge dropping the name is caught here."""
    assert "init_chat_model" in MODEL_CLASSES


def test_finds_init_chat_model_as_an_agent_definition() -> None:
    """A model loaded by the factory function is an AGENT_DEF at its own line."""
    surface = only(find_agent_defs(parse_snippet(INIT_CHAT_MODEL_SOURCE), FILE))
    assert (surface.kind, surface.name, surface.line) == (AGENT_DEF, "init_chat_model", 3)


def test_init_chat_model_records_the_module_it_was_imported_from() -> None:
    """The SBOM join reads `module`: a surface without one resolves to no package."""
    surface = only(find_agent_defs(parse_snippet(INIT_CHAT_MODEL_SOURCE), FILE))
    assert surface.module == "langchain.chat_models"
