"""Which name a call's result was bound to, within one file.

A surface says a call happened at a line; it never says what the value was
called afterwards. The taint trace is only as good as this half, so the cases
here are the assignment forms a real file uses -- and, just as important, the
ones that bind nothing at all, because a name bound by mistake would carry
taint that was never there.

The scope cases at the bottom are the same concern one level up: two functions,
or two methods of one class, binding the same name are two bindings.

`receiver_name` and `method_name` are tested as the pair they are: *which
object* is used and *what is asked of it*. The taint check needs both, and the
single `called_name` they replaced conflated them into a blind spot.
"""

import ast

from parsing.bindings import (
    Binding,
    argument_names,
    method_name,
    receiver_name,
    scoped_call_bindings,
)
from parsing.extractor_python import parse_file

# What the vulnerable app's main.py really binds, read off the file by hand.
# The four names an agent trace has to follow, written into one module so the
# line each is bound at can be counted by a reader. The pinned app this was
# verified against by hand is gone; the shape of the chain is what mattered.
AGENT_CHAIN_SOURCE = '''\
from langchain.agents import AgentExecutor, create_react_agent

if prompt := ChatPromptTemplate.from_template("answer {question}"):
    pass
llm = ChatLiteLLM(model="gpt-4o-mini")
chat_agent = create_react_agent(llm, [], prompt)
executor = AgentExecutor(agent=chat_agent, tools=[])
'''
AGENT_CHAIN_BINDINGS = {"prompt": 3, "llm": 5, "chat_agent": 6, "executor": 7}

# Two methods of one class binding the same name. A class body is not a scope
# its methods share, so this is two bindings and never one.
CLASS_METHODS = '''class Support:
    def build(self):
        agent = build_one()

    def rebuild(self):
        agent = build_other()
'''

BUILD_LINE = 3
REBUILD_LINE = 6


def merged_bindings(tree: ast.Module) -> dict[str, Binding]:
    """Merge every scope's bindings, for the tests that only ask "was it bound at all"."""
    merged: dict[str, Binding] = {}
    for scope in scoped_call_bindings(tree):
        merged.update(scope.bindings)
    return merged


def bindings_of(source: str) -> dict[str, Binding]:
    """Parse a snippet and return the names it binds from a call."""
    return merged_bindings(ast.parse(source))


def first_call(source: str) -> ast.Call:
    """Return the first call node in a snippet, for the three helpers that take one."""
    return next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Call))


def scopes_of(source: str) -> list:
    """Parse a snippet and return each scope with the names it binds."""
    return scoped_call_bindings(ast.parse(source))


def test_a_walrus_binds_the_name_to_the_call_line() -> None:
    """`if prompt := st.chat_input(...)` is how a real Streamlit app takes its input."""
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
    """A multi-line AgentExecutor call spans nine lines and is anchored on the first."""
    source = "executor = AgentExecutor.from_agent_and_tools(\n    tools=tools,\n)\n"
    assert bindings_of(source)["executor"].line == 1


def test_an_empty_module_binds_nothing() -> None:
    """Nothing to follow is a real answer, not an error."""
    assert bindings_of("") == {}


def test_argument_names_returns_positional_names() -> None:
    """A tainted name reaches a sink positionally, the shape the trace can follow."""
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


def test_receiver_name_returns_the_plain_name_being_called() -> None:
    """`executor(prompt)` is how a bound sink is invoked, and the callee is the receiver."""
    assert receiver_name(first_call("executor(prompt)")) == "executor"


def test_receiver_name_returns_the_object_a_method_is_called_on() -> None:
    """`agent.invoke(prompt)` uses the object named `agent`, which a binding can match.

    This is the case the deleted `called_name` answered `""` to. It asserted
    the defect: the receiver of the modern LangChain spelling is a local name,
    and reading it as "no name" is what made the taint trace silently blind.
    """
    assert receiver_name(first_call("agent.invoke(prompt)")) == "agent"


def test_receiver_name_is_empty_for_a_deeper_attribute_chain() -> None:
    """`a.b.c(prompt)` is called on the *value* of `a.b`, which this file never bound."""
    assert receiver_name(first_call("a.b.c(prompt)")) == ""


def test_method_name_is_still_the_method_when_the_receiver_is_empty() -> None:
    """The one input where the pair disagrees: no receiver, but the method is known.

    `a.b.c(prompt)` gives `""` from `receiver_name` and `"c"` from `method_name`.
    That divergence is intended -- the helpers answer two questions, and only the
    receiver half is unresolvable here -- so it is asserted rather than left to
    look like an oversight. It is also what makes the deep chain a *silent* miss
    in `test_taint_defect.py`: `taint.py` gates on the receiver first, so the
    call is dropped before the method it could have judged is ever consulted.
    """
    assert method_name(first_call("a.b.c(prompt)")) == "c"


def test_receiver_name_is_empty_for_a_call_on_a_call_result() -> None:
    """`factory()(prompt)` has no name to match a binding against either."""
    assert receiver_name(first_call("factory()(prompt)")) == ""


def test_method_name_returns_the_method_called_on_the_receiver() -> None:
    """*What* is asked of the object, which decides whether the call consumes the value."""
    assert method_name(first_call("agent.invoke(prompt)")) == "invoke"


def test_method_name_is_empty_for_a_bare_call() -> None:
    """`executor(prompt)` names no method, and the empty string says so."""
    assert method_name(first_call("executor(prompt)")) == ""


def test_a_whole_agent_chain_binds_every_name_the_trace_depends_on(tmp_path) -> None:
    """The walrus prompt, the model, the agent and the executor, each at its own line."""
    module = tmp_path / "main.py"
    module.write_text(AGENT_CHAIN_SOURCE, encoding="utf-8")
    bindings = merged_bindings(parse_file(module))
    found = {name: bindings[name].line for name in AGENT_CHAIN_BINDINGS if name in bindings}
    assert found == AGENT_CHAIN_BINDINGS


def test_two_methods_binding_the_same_name_keep_one_binding_each() -> None:
    """Merging them would read the second method's object as the first method's."""
    lines = sorted(scope.bindings["agent"].line for scope in scopes_of(CLASS_METHODS))
    assert lines == [BUILD_LINE, REBUILD_LINE]


def test_a_class_body_does_not_sweep_its_methods_bindings_into_the_top_level() -> None:
    """The class is excluded from the module's own statements, so it binds nothing there."""
    scopes = scopes_of(CLASS_METHODS)
    assert [sorted(scope.bindings) for scope in scopes] == [["agent"], ["agent"]]
