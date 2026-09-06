"""A function scope sees the module's names too, and its own first.

`scoped_call_bindings` used to give each function only what its own body bound,
which made the shape of every script-style LLM app invisible: the client built
once at import time and used inside the function that answers. The source was
bound in one scope, the sink in another, and the taint trace matched them in
neither -- no finding, and no probe either.

Merging the module's bindings underneath each function's own is how Python reads
a module, so this file pins both halves of that sentence: the module's names are
*there*, and a function that binds the same name is talking about its own. The
opposite direction is pinned too, because a merge is easy to write too widely: a
name bound inside a function must not appear at module level, and two sibling
functions must not see each other's.

`tests/checks/test_taint_module_scope.py` is the same change seen through
`trace_file` -- what a reader of findings.json gets. This file is the mechanism.
"""

import ast

from parsing.bindings import scoped_call_bindings

# The script-style app, reduced: one client at import time, one function using it.
MODULE_CLIENT = '''client = OpenAI()

def answer(question):
    prompt = build_prompt(question)
    return client.chat(prompt)
'''

MODULE_CLIENT_LINE = 1
LOCAL_CLIENT_LINE = 4

# The same file with the function building a client of its own. The only
# difference from MODULE_CLIENT is line 4, and that line is the whole test.
REBOUND_LOCALLY = '''client = OpenAI()

def answer(question):
    client = OpenAI(base_url=LOCAL_PROXY)
    return client.chat(question)
'''

# A name bound inside a function, and a module that must not see it.
BOUND_IN_A_FUNCTION = '''def build():
    helper = make_helper()

client = OpenAI()
'''

# Two functions that share no names at all, module level or otherwise.
TWO_FUNCTIONS = '''def take_input():
    question = st.chat_input("ask")

def answer():
    agent = build_agent()
    return agent
'''


def scopes_of(source: str) -> list:
    """Parse a snippet and return each scope with the names it can see."""
    return scoped_call_bindings(ast.parse(source))


def visible_names(source: str) -> list[list[str]]:
    """The names each scope can see, module scope first."""
    return [sorted(scope.bindings) for scope in scopes_of(source)]


def test_a_function_scope_sees_the_modules_bindings() -> None:
    """`client` is bound at import time and used in `answer`: the miss this change closed."""
    assert visible_names(MODULE_CLIENT) == [["client"], ["client", "prompt"]]


def test_the_inherited_name_still_points_at_the_line_the_module_bound_it_on() -> None:
    """A name is only useful to the trace if it carries the call it came from."""
    function_scope = scopes_of(MODULE_CLIENT)[1]
    assert function_scope.bindings["client"].line == MODULE_CLIENT_LINE


def test_a_local_binding_of_the_same_name_wins() -> None:
    """A function assigning `client` is talking about its own, and so is the trace."""
    function_scope = scopes_of(REBOUND_LOCALLY)[1]
    assert function_scope.bindings["client"].line == LOCAL_CLIENT_LINE


def test_the_module_scope_keeps_its_own_binding_when_a_function_rebinds_it() -> None:
    """The merge runs one way: the function's `client` must not overwrite the module's."""
    module_scope = scopes_of(REBOUND_LOCALLY)[0]
    assert module_scope.bindings["client"].line == MODULE_CLIENT_LINE


def test_the_module_scope_does_not_see_a_name_bound_inside_a_function() -> None:
    """The guard on the other side: merging both ways would join two unrelated scopes."""
    assert visible_names(BOUND_IN_A_FUNCTION) == [["client"], ["client", "helper"]]


def test_two_sibling_functions_do_not_see_each_others_names() -> None:
    """`question` in one function and `agent` in the other are two scopes, not one."""
    assert visible_names(TWO_FUNCTIONS) == [["question"], ["agent"]]
