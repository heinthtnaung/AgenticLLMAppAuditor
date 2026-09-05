"""The counting rule behind the vocabulary-coverage number, pinned table by table.

The number this module produces goes in the write-up, so what it counts has to
be checkable: a name is counted when a framework published it, once per language
however many tables hold it, and never for an HTTP verb, a chat-message key, an
object-name root or a substring the app author chose. Those exclusions are what
keeps the total honest, so each one is asserted here rather than trusted to the
docstring that explains it.

The measured totals over a whole pinned application went with the corpus that
held it. What is left is the rule, one exclusion at a time.
"""

from collections import Counter

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

# Every counted name more than one table of its language holds, written out
# rather than derived. Deriving it would make the union-versus-sum assertion
# below an identity that holds for any tables at all; as literals it says
# *which* names are doubled, and firing means a seventh appeared.
#
# Two Python table *pairs* overlap, on seven names between them, for two
# different reasons -- and both are deliberate: the five high-privilege tools
# are in TOOL_CLASSES for what they are and in HIGH_PRIVILEGE_TOOLS for what
# they reach, and both dataset loaders are in DATA_SOURCE_CALLS and
# DATA_SOURCE_METHODS because those match different call *shapes* -- the bare
# call needs the full-name table, any receiver form needs the leaf table.
# Either way it is one name a framework published once.
DOUBLED_PYTHON_NAMES = frozenset({
    "ShellTool", "PythonREPLTool", "PythonAstREPLTool",
    "RequestsGetTool", "RequestsPostTool",
    "load_dataset", "load_from_disk",
})
DOUBLED_JAVASCRIPT_NAMES = frozenset({
    "ShellTool", "WebBrowser", "JavaScriptInterpreter"})

DOUBLED_NAMES_MESSAGE = (
    "a name moved into or out of a second counted table. The counting rule is "
    "unchanged -- a name a framework published once is counted once -- but the "
    "list of names it applies to is pinned, so update it here."
)

# Registered for both languages since the Python tables gained them. What is
# left of the docs/TODO.md gap is below: the same three names are spread across
# the two languages differently, so the disagreement moved rather than closing.
NOW_IN_BOTH_LANGUAGES = ("ToolNode", "TavilySearchResults")

# Python-only, because the JavaScript tables carry the older spelling alone.
PYTHON_ONLY_TAVILY = "TavilySearch"

GAP_MOVED_MESSAGE = (
    "the two languages now agree about this name. That is the rest of the "
    "docs/TODO.md cross-language gap closing, which is good news: tick the "
    "task, and update this test."
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


def names_held_by_two_tables(module) -> set[str]:
    """Every counted name that more than one of a module's tables holds."""
    held = Counter(name for table in API_NAME_TABLES for name in set(getattr(module, table, ())))
    return {name for name, tables in held.items() if tables > 1}


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
    """The Python total is the union of the tables: the sum, less each name held twice.

    It used to subtract one table pair, `TOOL_CLASSES & HIGH_PRIVILEGE_TOOLS`,
    because that was the only overlap there could be. `load_from_disk` in both
    data-source tables is the second, so the rule is stated over every doubled
    name instead of over one pair of tables.
    """
    assert names_held_by_two_tables(detector_names) == DOUBLED_PYTHON_NAMES, DOUBLED_NAMES_MESSAGE
    assert DOUBLED_PYTHON_NAMES <= registered_names(PYTHON)
    assert (len(registered_names(PYTHON))
            == sum_of_table_sizes(detector_names) - len(DOUBLED_PYTHON_NAMES))


def test_a_javascript_name_in_two_tables_is_counted_once() -> None:
    """The same union rule holds on the JavaScript side, which overlaps on three tools."""
    assert names_held_by_two_tables(detector_names_js) == DOUBLED_JAVASCRIPT_NAMES, \
        DOUBLED_NAMES_MESSAGE
    assert DOUBLED_JAVASCRIPT_NAMES <= registered_names(JAVASCRIPT)
    assert (len(registered_names(JAVASCRIPT))
            == sum_of_table_sizes(detector_names_js) - len(DOUBLED_JAVASCRIPT_NAMES))


def test_the_python_overlaps_are_the_two_deliberate_table_pairs() -> None:
    """Two *pairs*, seven names: which tables overlap and why, so a third is noticed.

    The count in the name is pairs of tables, not names -- five tools come from
    one pair and two dataset loaders from the other. A doubled name is not a
    mistake to be cleaned up: it is one published API name matched two ways.
    `ShellTool` is a tool *and* a high-privilege one; `load_dataset` is matched
    as a whole call name *and* as a leaf on any receiver. What would be a
    mistake is a doubling nobody meant, which is why the pairs are named.
    """
    tools = detector_names.TOOL_CLASSES & detector_names.HIGH_PRIVILEGE_TOOLS
    data_sources = set(detector_names.DATA_SOURCE_CALLS) & set(detector_names.DATA_SOURCE_METHODS)
    assert OVERLAPPING_PYTHON_TOOL in tools
    assert data_sources == {"load_dataset", "load_from_disk"}
    assert tools | data_sources == DOUBLED_PYTHON_NAMES


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
    """An app's own function is a surface, but it is not a framework name any key tested."""
    result = coverage(PYTHON, [surface("my_own_helper")])
    assert result["exercised"] == 0
    assert result["exercised_names"] == []


def test_coverage_reports_the_language_it_was_asked_about() -> None:
    """The document names its subject, so two languages' results cannot be confused."""
    assert coverage(JAVASCRIPT, [])["language"] == JAVASCRIPT


# --- A known gap, pinned so closing it is noticed --------------------------

def test_toolnode_and_the_older_tavily_name_are_registered_for_both_languages() -> None:
    """The gap TODO.md recorded: the Python tables now name what the JS ones did."""
    javascript = registered_names(JAVASCRIPT)
    python = registered_names(PYTHON)
    for name in NOW_IN_BOTH_LANGUAGES:
        assert name in javascript
        assert name in python


def test_the_newer_tavily_spelling_is_registered_for_python_only() -> None:
    """What is left of the gap: `TavilySearch` is named in one language, not both."""
    assert PYTHON_ONLY_TAVILY in registered_names(PYTHON)
    assert PYTHON_ONLY_TAVILY not in registered_names(JAVASCRIPT), \
        f"{PYTHON_ONLY_TAVILY}: {GAP_MOVED_MESSAGE}"


def test_the_two_languages_file_toolnode_under_different_tables() -> None:
    """Pinned because it changes the surface kind, not just the count.

    Python names `ToolNode` a tool class, so `ToolNode([search])` extracts as a
    TOOL_CALL; JavaScript names it an agent factory -- its table says counting
    it as a tool would double-count the tools it wires up -- so the same
    construct extracts as an AGENT_DEF there. The vocabulary total is blind to
    this, since it is the union of the tables; a grading key joining on
    `llm_surface`, and any check filtering on kind, are not.
    """
    assert "ToolNode" in detector_names.TOOL_CLASSES
    assert "ToolNode" not in detector_names.AGENT_FACTORIES
    assert "ToolNode" in detector_names_js.AGENT_FACTORIES
    assert "ToolNode" not in detector_names_js.TOOL_CLASSES

