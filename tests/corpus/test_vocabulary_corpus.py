"""How much of the detector vocabulary the corpus really exercises, as measured numbers.

Every figure here was read off a real extraction of the three fixtures. They are
written down rather than recomputed, because the write-up quotes them: the prose
figure this replaced ("57 names across 12 tables") reproduced under no reading of
the source, and the only way a stale number cannot come back is for the current
one to be a test that fails when it moves.

Two ways this file fails, and both are the point. A table gains or loses a name
and `registered` moves; a fixture starts or stops reaching a name and
`exercised_names` moves. Either way the number in the write-up is wrong and this
says so.
"""

import pytest

from artifacts.surface import Surface
from conftest import app_path, require_corpus
from dependency_fixtures import REACT_AGENT, corpus_surfaces, js_surfaces
from evaluation.vocabulary import coverage
from parsing.extractor import extract_repo
from parsing.languages import JAVASCRIPT, PYTHON

# Measured over vuln-app-1-support-agent and oss-app-react-agent together:
# 6 of the 76 names the Python tables register are reached by any fixture.
PYTHON_COVERAGE = {
    "language": PYTHON,
    "registered": 76,
    "exercised": 12,
    "untested": 64,
    "exercised_names": [
        "AgentExecutor", "ChatLiteLLM", "ConversationalChatAgent", "StateGraph",
        "execute", "executemany", "fetchall", "load", "os.environ.get",
        "os.getenv", "st.chat_input", "yaml.load",
    ],
}

# Measured over oss-app-langgraphjs-starter: 4 of 42.
JAVASCRIPT_COVERAGE = {
    "language": JAVASCRIPT,
    "registered": 42,
    "exercised": 4,
    "untested": 38,
    "exercised_names": ["ChatOpenAI", "StateGraph", "TavilySearchResults", "ToolNode"],
}

# What the two languages carry between them, restated so the headline figure the
# write-up quotes is itself asserted rather than left to a reader's addition.
TOTAL_REGISTERED = 118
TOTAL_UNTESTED = 102


@pytest.fixture(scope="module")
def python_surfaces() -> list[Surface]:
    """Every Python surface the corpus holds: the vulnerable app plus the clean template."""
    require_corpus(REACT_AGENT)
    return corpus_surfaces() + extract_repo(str(app_path(REACT_AGENT))).surfaces


@pytest.fixture(scope="module")
def javascript_surfaces() -> list[Surface]:
    """The TypeScript starter's surfaces, the corpus's only non-Python app."""
    return js_surfaces()


def test_the_python_fixtures_exercise_twelve_of_seventy_six_names(
        python_surfaces: list[Surface]) -> None:
    """Measured: 6 reached, 70 carried untested, over both Python fixtures."""
    assert coverage(PYTHON, python_surfaces) == PYTHON_COVERAGE


def test_the_javascript_fixture_exercises_four_of_forty_two_names(
        javascript_surfaces: list[Surface]) -> None:
    """Measured: 4 reached, 38 carried untested, over the one TypeScript fixture."""
    assert coverage(JAVASCRIPT, javascript_surfaces) == JAVASCRIPT_COVERAGE


def test_the_corpus_leaves_a_hundred_and_two_of_a_hundred_and_eighteen_names_untested(
        python_surfaces: list[Surface], javascript_surfaces: list[Surface]) -> None:
    """The headline figure: most of the vocabulary is code the corpus cannot speak for."""
    python = coverage(PYTHON, python_surfaces)
    javascript = coverage(JAVASCRIPT, javascript_surfaces)
    assert python["registered"] + javascript["registered"] == TOTAL_REGISTERED
    assert python["untested"] + javascript["untested"] == TOTAL_UNTESTED


def test_the_vulnerable_app_reaches_the_yaml_load_name_its_key_grades(
        python_surfaces: list[Surface]) -> None:
    """One reached name is a graded finding's surface, so coverage and scoring agree."""
    assert "yaml.load" in coverage(PYTHON, python_surfaces)["exercised_names"]


def test_the_javascript_fixtures_tool_names_are_not_credited_to_python(
        javascript_surfaces: list[Surface]) -> None:
    """The gap from the corpus side: two names a JS fixture reaches and Python never registered."""
    reached = coverage(PYTHON, javascript_surfaces)["exercised_names"]
    assert "ToolNode" not in reached
    assert "TavilySearchResults" not in reached
