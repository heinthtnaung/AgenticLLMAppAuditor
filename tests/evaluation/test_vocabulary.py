"""The counting rule behind the vocabulary-coverage number, pinned table by table.

The number this module produces goes in the write-up, so what it counts has to
be checkable: a name is counted when a framework published it, once per language
however many tables hold it, and never for an HTTP verb, a chat-message key, an
object-name root or a substring the app author chose. Those exclusions are what
keeps the total honest, so each one is asserted here rather than trusted to the
docstring that explains it.

The corpus-wide totals live in tests/corpus/test_vocabulary_corpus.py, which is
where a measured figure belongs.
"""

import pytest

from artifacts.surface import DATA_SOURCE, Surface
from detectors import detector_names, detector_names_js
from evaluation.vocabulary import (
    API_NAME_TABLES,
    coverage,
    exercised_names,
    registered_names,
)
from parsing.languages import JAVASCRIPT, PYTHON

# A tool both TOOL_CLASSES and HIGH_PRIVILEGE_TOOLS name, in each language.
# The two tables overlap on purpose -- one says what it is, the other what it
# can reach -- so the total must be the union of them, never the sum.
OVERLAPPING_PYTHON_TOOL = "ShellTool"
OVERLAPPING_JAVASCRIPT_TOOL = "WebBrowser"

# Registered for JavaScript, absent from the Python tables. docs/TODO.md carries
# closing this as an open task; the assertions below say so when it closes.
CROSS_LANGUAGE_GAP = ("ToolNode", "TavilySearchResults")

GAP_CLOSED_MESSAGE = (
    "is now registered for Python. That is the known cross-language gap in "
    "docs/TODO.md being closed, which is good news: tick the task, and update "
    "this test and the pinned Python totals in tests/corpus/test_vocabulary_corpus.py."
)

UNKNOWN_LANGUAGE = "cobol"


def surface(name: str) -> Surface:
    """One surface carrying a name, built through the real record rather than a stand-in."""
    return Surface(kind=DATA_SOURCE, name=name, file="app.py", line=1,
                   language=PYTHON, detail="", module="")


def table_of(module, table: str) -> set[str]:
    """Read one name table off a detector-names module as a set."""
    return set(getattr(module, table))


def sum_of_table_sizes(module) -> int:
    """Add up the counted tables without deduplicating, so the union can be compared to it."""
    return sum(len(getattr(module, table, ())) for table in API_NAME_TABLES)


# --- What is counted -------------------------------------------------------

def test_a_framework_class_the_detectors_look_for_is_registered() -> None:
    """The ordinary case: a LangChain model class is a name a framework published."""
    assert "ChatOpenAI" in registered_names(PYTHON)


def test_a_dotted_data_source_call_is_registered_under_its_full_name() -> None:
    """DATA_SOURCE_CALLS keys are counted whole, not split at the dot."""
    assert "os.environ.get" in registered_names(PYTHON)


def test_each_language_has_its_own_registered_set() -> None:
    """Python's tables and JavaScript's are read separately; neither answers for the other."""
    assert "create_react_agent" in registered_names(PYTHON)
    assert "create_react_agent" not in registered_names(JAVASCRIPT)


# --- What is excluded, and why ---------------------------------------------

def test_author_chosen_prompt_name_hints_are_not_registered() -> None:
    """PROMPT_NAME_HINTS are substrings of names the app author picked, not API names."""
    assert "system_msg" in detector_names.PROMPT_NAME_HINTS
    assert table_of(detector_names, "PROMPT_NAME_HINTS") & registered_names(PYTHON) == set()


def test_chat_message_text_keys_are_not_registered() -> None:
    """MESSAGE_TEXT_KEYS are dict keys inside a message -- `content`, `text` -- not classes."""
    assert "content" in detector_names_js.MESSAGE_TEXT_KEYS
    assert table_of(detector_names_js, "MESSAGE_TEXT_KEYS") & registered_names(JAVASCRIPT) == set()


def test_http_verbs_are_not_registered() -> None:
    """`get` and `post` are verbs any router spells; counting them inflates every total."""
    assert {"get", "post"} <= detector_names.HTTP_METHODS
    assert table_of(detector_names, "HTTP_METHODS") & registered_names(PYTHON) == set()
    assert table_of(detector_names_js, "ROUTE_METHODS") & registered_names(JAVASCRIPT) == set()


def test_route_object_roots_are_not_registered() -> None:
    """`app` and `router` are conventional variable names, published by nobody."""
    assert {"app", "router"} == set(detector_names.ROUTE_DECORATOR_ROOTS)
    assert table_of(detector_names, "ROUTE_DECORATOR_ROOTS") & registered_names(PYTHON) == set()
    assert table_of(detector_names_js, "ROUTE_OBJECTS") & registered_names(JAVASCRIPT) == set()


# --- Deduplication ---------------------------------------------------------

def test_a_python_name_in_two_tables_is_counted_once() -> None:
    """The Python total is the union of the tables: the sum, less the tools named twice."""
    counted_twice = detector_names.TOOL_CLASSES & detector_names.HIGH_PRIVILEGE_TOOLS
    assert OVERLAPPING_PYTHON_TOOL in counted_twice
    assert OVERLAPPING_PYTHON_TOOL in registered_names(PYTHON)
    assert len(registered_names(PYTHON)) == sum_of_table_sizes(detector_names) - len(counted_twice)


def test_a_javascript_name_in_two_tables_is_counted_once() -> None:
    """The same union rule holds on the JavaScript side, which overlaps on three tools."""
    counted_twice = detector_names_js.TOOL_CLASSES & detector_names_js.HIGH_PRIVILEGE_TOOLS
    assert OVERLAPPING_JAVASCRIPT_TOOL in counted_twice
    assert OVERLAPPING_JAVASCRIPT_TOOL in registered_names(JAVASCRIPT)
    assert (len(registered_names(JAVASCRIPT))
            == sum_of_table_sizes(detector_names_js) - len(counted_twice))


# --- Failing clearly -------------------------------------------------------

def test_an_unknown_language_raises_naming_the_languages_it_knows() -> None:
    """Rule 8: a language with no tables is an error that says what it could have been."""
    with pytest.raises(ValueError) as raised:
        registered_names(UNKNOWN_LANGUAGE)
    message = str(raised.value)
    assert UNKNOWN_LANGUAGE in message
    assert PYTHON in message
    assert JAVASCRIPT in message


def test_coverage_rejects_an_unknown_language_too() -> None:
    """The error is raised before any counting, so coverage cannot report an empty set instead."""
    with pytest.raises(ValueError):
        coverage(UNKNOWN_LANGUAGE, [surface("ChatOpenAI")])


# --- What a scan reached ---------------------------------------------------

def test_exercised_names_returns_the_registered_names_the_scan_reached() -> None:
    """Only registered names come back: a scan reaching nothing registered reaches nothing."""
    registered = {"ChatOpenAI", "yaml.load", "StateGraph"}
    assert exercised_names([surface("ChatOpenAI"), surface("yaml.load")], registered) == {
        "ChatOpenAI", "yaml.load"}


def test_a_receiver_qualified_surface_reaches_the_registered_method() -> None:
    """A detector matches a root and names the chain, so `cursor.execute` reaches `execute`.

    Comparing whole names undercounts, and it undercounts flatteringly: it
    reported `AgentExecutor` untested while a graded key entry rests on it.
    """
    assert exercised_names([surface("cursor.execute")], {"execute"}) == {"execute"}
    assert exercised_names([surface("AgentExecutor.from_agent_and_tools")],
                           {"AgentExecutor"}) == {"AgentExecutor"}


def test_an_unrelated_name_sharing_a_substring_is_not_reached() -> None:
    """Segments, not substrings: `execute` must not be credited by `executemany_helper`."""
    assert exercised_names([surface("executemany_helper")], {"execute"}) == set()


def test_an_empty_scan_exercises_no_names() -> None:
    """No surfaces means no names reached -- not an error, and not everything."""
    assert exercised_names([], {"ChatOpenAI"}) == set()


def test_an_empty_scan_leaves_every_registered_name_untested() -> None:
    """Coverage of nothing reports zero exercised and the whole vocabulary untested."""
    result = coverage(PYTHON, [])
    assert result["exercised"] == 0
    assert result["exercised_names"] == []
    assert result["untested"] == result["registered"] == len(registered_names(PYTHON))


def test_a_name_no_table_holds_is_not_counted_as_exercised() -> None:
    """An app's own function is a surface, but it is not a framework name the corpus tested."""
    result = coverage(PYTHON, [surface("my_own_helper")])
    assert result["exercised"] == 0
    assert result["exercised_names"] == []


def test_coverage_reports_the_language_it_was_asked_about() -> None:
    """The document names its subject, so two languages' results cannot be confused."""
    assert coverage(JAVASCRIPT, [])["language"] == JAVASCRIPT


# --- A known gap, pinned so closing it is noticed --------------------------

def test_toolnode_and_tavily_are_registered_for_javascript_only() -> None:
    """Pins the open TODO.md gap: the two languages disagree about the same libraries."""
    javascript = registered_names(JAVASCRIPT)
    python = registered_names(PYTHON)
    for name in CROSS_LANGUAGE_GAP:
        assert name in javascript
        assert name not in python, f"{name} {GAP_CLOSED_MESSAGE}"
