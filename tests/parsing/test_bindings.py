"""Which name a call's result was bound to, within one file.

A surface says a call happened at a line; it never says what the value was
called afterwards. The taint trace is only as good as this half, so the cases
here are the assignment forms a real file uses -- and, just as important, the
ones that bind nothing at all, because a name bound by mistake would carry
taint that was never there.
"""

import ast

from conftest import app_path, require_corpus
from dependency_fixtures import SUPPORT_AGENT
from parsing.bindings import Binding, argument_names, call_bindings, called_name
from parsing.extractor_python import parse_file

# What the vulnerable app's main.py really binds, read off the file by hand.
CORPUS_BINDINGS = {"prompt": 60, "llm": 63, "chat_agent": 69, "executor": 71}


def bindings_of(source: str) -> dict[str, Binding]:
    """Parse a snippet and return the names it binds from a call."""
    return call_bindings(ast.parse(source))


def first_call(source: str) -> ast.Call:
    """Return the first call node in a snippet, for the two helpers that take one."""
    return next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Call))


def test_a_walrus_binds_the_name_to_the_call_line() -> None:
    """`if prompt := st.chat_input(...)` is how the corpus app takes its input."""
    assert bindings_of("if prompt := st.chat_input('ask'):\n    pass\n")["prompt"] == \
        Binding("prompt", 1)


def test_a_plain_assignment_binds_the_name_to_the_call_line() -> None:
    """The ordinary case: one name, one call."""
    assert bindings_of("executor = build_agent()\n")["executor"] == Binding("executor", 1)


def test_an_annotated_assignment_binds_the_name() -> None:
    """A type annotation is still an assignment, and must not hide the binding."""
    assert bindings_of("llm: ChatModel = ChatLiteLLM()\n")["llm"] == Binding("llm", 1)


def test_a_tuple_target_binds_every_name_to_the_same_call() -> None:
    """Both halves of `a, b = f()` hold part of one call's result."""
    bindings = bindings_of("first, second = split_result()\n")
    assert bindings["first"] == Binding("first", 1)
    assert bindings["second"] == Binding("second", 1)


def test_a_later_binding_wins() -> None:
    """A reader sees the name as whatever it was last assigned before it is used."""
    assert bindings_of("agent = build_one()\nagent = build_other()\n")["agent"].line == 2


def test_a_value_that_is_not_a_call_binds_nothing() -> None:
    """`x = 1` holds no call result, so it can carry no taint from one."""
    assert bindings_of("prompt = 'hardcoded'\ncount = 1\n") == {}


def test_an_attribute_target_binds_no_plain_name() -> None:
    """`self.agent = f()` binds an attribute, which this module deliberately cannot follow."""
    assert bindings_of("self.agent = build_agent()\n") == {}


def test_a_subscript_target_binds_no_plain_name() -> None:
    """`store['agent'] = f()` is the same case: no plain name is bound."""
    assert bindings_of("store['agent'] = build_agent()\n") == {}


def test_a_call_used_but_never_assigned_binds_nothing() -> None:
    """A bare call statement is exactly the case the taint probe reports as unfollowed."""
    assert bindings_of("st.chat_input('ask')\n") == {}


def test_a_nested_call_does_not_bind_the_outer_name() -> None:
    """The outer call's result is named; the inner call's result never was."""
    bindings = bindings_of("value = outer(\n    inner()\n)\n")
    assert bindings == {"value": Binding("value", 1)}


def test_a_multi_line_call_binds_the_line_it_starts_on() -> None:
    """The corpus app's AgentExecutor call spans nine lines and is anchored on the first."""
    source = "executor = AgentExecutor.from_agent_and_tools(\n    tools=tools,\n)\n"
    assert bindings_of(source)["executor"].line == 1


def test_an_empty_module_binds_nothing() -> None:
    """Nothing to follow is a real answer, not an error."""
    assert bindings_of("") == {}


def test_argument_names_returns_positional_names() -> None:
    """A tainted name reaches a sink positionally in the corpus app."""
    assert argument_names(first_call("executor(prompt, other)")) == {"prompt", "other"}


def test_argument_names_returns_keyword_names() -> None:
    """Passing by keyword carries the same value, so it must be seen too."""
    assert argument_names(first_call("executor(user_input=prompt)")) == {"prompt"}


def test_argument_names_ignores_anything_that_is_not_a_plain_name() -> None:
    """A literal, an attribute and a nested call name no variable that could be tainted."""
    assert argument_names(first_call("executor('literal', obj.attr, inner())")) == set()


def test_argument_names_of_a_call_with_no_arguments_is_empty() -> None:
    """No arguments means nothing was handed over."""
    assert argument_names(first_call("executor()")) == set()


def test_called_name_returns_the_plain_name_being_called() -> None:
    """`executor(prompt)` is how a bound sink is invoked."""
    assert called_name(first_call("executor(prompt)")) == "executor"


def test_called_name_is_empty_for_a_method_call() -> None:
    """`obj.method()` names no bare variable, and the empty string says so."""
    assert called_name(first_call("obj.method(prompt)")) == ""


def test_called_name_is_empty_for_a_call_on_a_call_result() -> None:
    """`factory()(prompt)` has no name to match a binding against either."""
    assert called_name(first_call("factory()(prompt)")) == ""


def test_the_corpus_app_binds_the_names_the_trace_depends_on() -> None:
    """Verified by hand against main.py: the walrus prompt, the model, the agent, the executor."""
    require_corpus(SUPPORT_AGENT)
    bindings = call_bindings(parse_file(app_path(SUPPORT_AGENT) / "main.py"))
    found = {name: bindings[name].line for name in CORPUS_BINDINGS if name in bindings}
    assert found == CORPUS_BINDINGS
