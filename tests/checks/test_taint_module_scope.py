"""The script-style app: the model built at import time, the call inside a function.

This was the taint trace's largest silent miss, and it is the shape of most
small LLM apps -- `client = OpenAI()` and `question = st.chat_input(...)` at
module level, `client.invoke(question)` inside the function that answers. Each
scope used to see only the names its own body bound, so the source sat in one
map and the sink in another, and the check produced **no finding and no probe**:
an audit that read as "traced, found nothing" over a flow that was there.

`scoped_call_bindings` now merges the module's bindings into every function
scope, the module's underneath the function's own. Both halves are pinned here
through `trace_file`, which is what a reader of findings.json actually gets:
the flow is reported, and a function that binds the same name over the module's
is talking about its own.

The last test is the cost of the merge and is written as such. Only a rebinding
*to a call* shadows, because only a call is a binding this module records, so a
function that assigns a literal over a module-level source keeps the taint and
the finding names a value that function never used. Loud and arguable rather
than silent, which is the direction this project chose -- but it is a positive
claim, and a reader should meet it here.

The mechanism itself is pinned in `tests/parsing/test_bindings_scope_merge.py`.
Every snippet is written in this file: what the check sees is an `ast` tree plus
the surfaces the extractor reported, and both are three lines to build.
"""

from artifacts.surface import AGENT_DEF, DATA_SOURCE
from test_taint import AGENT_NAME, FILE, SOURCE_NAME, surface, trace

SOURCE_LINE = 1
AGENT_LINE = 2

# The script-style app, reduced to the four lines that carry the flow.
MODULE_SCOPE_APP = '''question = st.chat_input("ask")
agent = AgentExecutor.from_agent_and_tools(tools=tools)

def answer():
    return agent.invoke(question)
'''

# The same file with the function building an agent of its own. `agent` inside
# `answer` is that agent, not the module's, so the module's sink is never used.
REBOUND_SINK = '''question = st.chat_input("ask")
agent = AgentExecutor.from_agent_and_tools(tools=tools)

def answer():
    agent = build_local_stub()
    return agent.invoke(question)
'''

# The one line that makes the difference, so "no finding" cannot come from a
# snippet that was mis-typed into something the trace never had a chance on.
REBINDING_LINE = "    agent = build_local_stub()"

# The same file again, with the *source* name rebound to a literal instead. Not
# a binding this module records, so the module's `question` survives it.
REBOUND_TO_A_LITERAL = '''question = st.chat_input("ask")
agent = AgentExecutor.from_agent_and_tools(tools=tools)

def answer():
    question = "how do I reset my password?"
    return agent.invoke(question)
'''

# The merge runs one way. A name bound inside a function is not a module name,
# and the call at module level is reading something else entirely.
SOURCE_INSIDE_A_FUNCTION = '''def take_input():
    question = st.chat_input("ask")

agent = AgentExecutor.from_agent_and_tools(tools=tools)
answer = agent.invoke(question)
'''

LOCAL_SOURCE_LINE = 2
LOCAL_AGENT_LINE = 4


def trace_script(snippet: str) -> tuple:
    """Trace a script-style app whose source is on line 1 and whose agent is on line 2."""
    return trace(snippet, [surface(DATA_SOURCE, SOURCE_NAME, SOURCE_LINE),
                           surface(AGENT_DEF, AGENT_NAME, AGENT_LINE)])


def reported_by(snippet: str) -> list[tuple[str, int]]:
    """Where the trace anchors each finding for one snippet."""
    findings, _probes = trace_script(snippet)
    return [(finding.file, finding.line) for finding in findings]


def test_a_module_level_source_reaches_a_sink_called_inside_a_function() -> None:
    """The miss this change closed, and the shape of every script-style LLM app."""
    assert reported_by(MODULE_SCOPE_APP) == [(FILE, SOURCE_LINE)]


def test_that_flow_leaves_no_probe_behind() -> None:
    """The trace reached a conclusion, so there is no gap left to report."""
    assert trace_script(MODULE_SCOPE_APP)[1] == []


def test_a_function_that_binds_its_own_sink_name_reports_nothing() -> None:
    """`agent` inside the function is the function's, so the module's sink is unused."""
    assert reported_by(REBOUND_SINK) == []


def test_the_shadowing_snippet_differs_by_exactly_the_rebinding_line() -> None:
    """The guard for the test above: a broken snippet also reports nothing."""
    without_the_rebinding = [line for line in REBOUND_SINK.splitlines()
                             if line != REBINDING_LINE]
    assert without_the_rebinding == MODULE_SCOPE_APP.splitlines()


def test_a_source_bound_inside_a_function_is_not_read_at_module_level() -> None:
    """Merging both ways would join a name in one scope to a call in another."""
    findings, _probes = trace(
        SOURCE_INSIDE_A_FUNCTION,
        [surface(DATA_SOURCE, SOURCE_NAME, LOCAL_SOURCE_LINE),
         surface(AGENT_DEF, AGENT_NAME, LOCAL_AGENT_LINE)])
    assert findings == []


def test_a_local_name_rebound_to_a_literal_shadows_the_module_source() -> None:
    """A name the function writes to at all is local, whatever it was written from.

    This pinned the opposite when it was written, as the honest cost of the
    merge: `_bindings_in` records only names bound to a *call*, so
    `question = "how do I reset my password?"` shadowed nothing, the module's
    untrusted `question` stayed visible, and the finding named a value the
    function never passed -- a false positive the merge introduced. Shadowing
    now follows any store, so the claim the merge's docstring makes is true.
    """
    assert reported_by(REBOUND_TO_A_LITERAL) == []
