"""How the sink is *called* -- the line between a finding and a false positive.

`test_taint.py` pins the trace itself: a source bound to a name, a sink bound to
a name, one handed to the other. This file pins the shape of that last call,
which two gates decide and which needs both:

* the **receiver** must be a name this file bound to a surface. `agent` in
  `agent.invoke(question)` is one; the receiver of `agent.runnable.invoke(...)`
  is a value, not a name, and cannot be matched against a binding.
* the **method** must be one that hands its arguments to the model. Resolving
  the receiver alone made *every* method on a surface-bound object count as a
  consumption, and `llm.bind(api_key=key)` came out as "untrusted input reaches
  the model" -- a false positive with a plausible shape, reproduced before it
  shipped. `.bind`, `.with_config` and `.add_node` are as common as `.invoke`
  on exactly those objects.

The method gate has **three** answers, and this file holds the two decided ones:
a name in `CONSUMING_METHODS` is a finding, a name in `CONFIGURING_METHODS` is
silence. The third -- a method in neither list, which is answered with an
`INCONCLUSIVE` probe rather than with silence -- lives in
`test_taint_unknown_method.py`, because "which methods consume a value" and
"what is said when we cannot judge one" are two questions.

Every "no finding" case here has a positive twin over the same snippet, so a
green result cannot come from a fixture that was mis-wired in the first place.
"""

from artifacts.surface import AGENT_DEF, DATA_SOURCE
from checks.taint import CONFIGURING_METHODS, CONSUMING_METHODS
from test_taint import AGENT_NAME, FILE, SOURCE_NAME, surface, trace

# The traced flow with its last line left open: the untrusted value at line 1,
# the agent at line 2, and the call that varies. Every agent test below differs
# from every other in that one line and nothing else.
AGENT_FLOW = ('question = st.chat_input("ask")\n'
              'agent = AgentExecutor.from_agent_and_tools(tools=tools)\n'
              'answer = {call}\n')

# The configuration case, built from surfaces the extractor really reports:
# `os.getenv` is a DATA_SOURCE and `ChatLiteLLM` an AGENT_DEF, so the receiver
# is genuinely surface-bound and the value genuinely untrusted. Only the call on
# line 3 decides whether this is a finding.
MODEL_CONFIG_FLOW = ('api_key = os.getenv("OPENAI_API_KEY")\n'
                     'llm = ChatLiteLLM(model="gpt-4o-mini")\n'
                     'configured = {call}\n')

ENV_SOURCE_NAME = "os.getenv"
MODEL_NAME = "ChatLiteLLM"

# Two names bound to calls that are no surface at all, beside an agent that is.
# The receiver gate is what refuses these, whatever the method is called.
BOUND_NON_SURFACES = ('question = st.chat_input("ask")\n'
                      'agent = AgentExecutor.from_agent_and_tools(tools=tools)\n'
                      'logger = logging.getLogger(__name__)\n'
                      'sanitiser = build_sanitiser()\n'
                      'answer = {call}\n')

# Where the untrusted value enters, in all three snippets: line 1.
SOURCE_LINE = 1

# The names added after `agent.generate(question)` was found to be neither
# reported nor probed. `predict`/`apredict` and `stream`/`astream` were already
# on the list while `generate` was not, which is the inconsistency they close.
LATER_CONSUMING_METHODS = (
    "generate", "agenerate", "predict_messages", "apredict_messages",
    "astream_events")

# Spellings each list must keep, whatever else is added to it: without them the
# disjointness test below would also pass over two emptied lists.
ANCHOR_CONSUMING = frozenset({"invoke", "ainvoke", "run", "generate", "astream_events"})
ANCHOR_CONFIGURING = frozenset({"bind", "with_config", "add_node", "compile"})


def trace_agent_call(call: str) -> tuple:
    """Trace the source-to-agent flow with the agent used by the given expression."""
    return trace(AGENT_FLOW.format(call=call),
                 [surface(DATA_SOURCE, SOURCE_NAME, 1),
                  surface(AGENT_DEF, AGENT_NAME, 2)])


def trace_model_config(call: str) -> tuple:
    """Trace an environment-variable value handed to the given call on a bound model."""
    return trace(MODEL_CONFIG_FLOW.format(call=call),
                 [surface(DATA_SOURCE, ENV_SOURCE_NAME, 1),
                  surface(AGENT_DEF, MODEL_NAME, 2)])


def trace_non_surface_call(call: str) -> tuple:
    """Trace the flow when the value goes to a bound name that is not a surface."""
    return trace(BOUND_NON_SURFACES.format(call=call),
                 [surface(DATA_SOURCE, SOURCE_NAME, 1),
                  surface(AGENT_DEF, AGENT_NAME, 2)])


def test_a_bare_call_on_the_agent_is_reported() -> None:
    """The guard for the two below: the snippets differ in that call and nothing else."""
    findings, _ = trace_agent_call("agent(question)")
    assert [(f.file, f.line) for f in findings] == [(FILE, SOURCE_LINE)]


def test_invoke_on_the_agent_is_reported() -> None:
    """`agent.invoke(question)` -- the modern LangChain spelling -- hands the value over."""
    findings, _ = trace_agent_call("agent.invoke(question)")
    assert [(f.file, f.line) for f in findings] == [(FILE, SOURCE_LINE)]


def test_run_on_the_agent_is_reported() -> None:
    """`agent.run(question)` is the older spelling of the same hand-over."""
    findings, _ = trace_agent_call("agent.run(question)")
    assert [(f.file, f.line) for f in findings] == [(FILE, SOURCE_LINE)]


def test_a_configuring_method_on_a_bound_model_is_not_reported() -> None:
    """`llm.bind(api_key=key)` settles the model; it does not feed it the key.

    The false positive the method gate exists to prevent, and the case that
    refuted resolving the receiver alone.
    """
    findings, _ = trace_model_config("llm.bind(api_key=api_key)")
    assert findings == []


def test_the_same_value_invoked_on_the_same_model_is_reported() -> None:
    """The twin of the test above: same source, same receiver, consuming method."""
    findings, _ = trace_model_config("llm.invoke(api_key)")
    assert [(f.file, f.line) for f in findings] == [(FILE, SOURCE_LINE)]


def test_add_node_on_a_bound_agent_is_not_reported() -> None:
    """`graph.add_node(...)` builds the workflow; the value is not handed to a model."""
    findings, _ = trace_agent_call("agent.add_node(question)")
    assert findings == []


def test_a_method_call_on_a_bound_logger_is_not_reported() -> None:
    """`logger.info(question)` names a bound receiver that is no surface at all."""
    findings, _ = trace_non_surface_call("logger.info(question)")
    assert findings == []


def test_a_consuming_method_on_a_name_that_is_no_surface_is_not_reported() -> None:
    """`sanitiser.invoke(question)` consumes the value; only the receiver gate refuses it."""
    findings, _ = trace_non_surface_call("sanitiser.invoke(question)")
    assert findings == []


def test_the_value_still_reaches_the_agent_in_the_same_snippet() -> None:
    """The twin of the two above: those names are not sinks, but `agent` in that file is."""
    findings, _ = trace_non_surface_call("agent.invoke(question)")
    assert [(f.file, f.line) for f in findings] == [(FILE, SOURCE_LINE)]


def test_a_deeper_attribute_chain_is_not_followed() -> None:
    """`agent.runnable.invoke(question)` is called on a value, not on a name this file bound.

    A decided boundary, not an oversight -- and the silence about it is the
    strict xfail in `test_taint_defect.py`, which is what will retire it.
    """
    findings, _ = trace_agent_call("agent.runnable.invoke(question)")
    assert findings == []


def test_the_later_added_consuming_methods_are_all_reported() -> None:
    """`agent.generate(question)` and its four siblings hand the value over like `.invoke` does.

    One test over the five rather than five near-identical ones: they were added
    together, for one reason, and what matters is that none of them was missed.
    """
    reported = {method: [(f.file, f.line) for f in trace_agent_call(f"agent.{method}(question)")[0]]
                for method in LATER_CONSUMING_METHODS}
    assert reported == {method: [(FILE, SOURCE_LINE)] for method in LATER_CONSUMING_METHODS}


def test_no_method_both_consumes_and_configures() -> None:
    """The lists are closed vocabularies: an overlap would let `_verdict` silently prefer one."""
    assert CONSUMING_METHODS & CONFIGURING_METHODS == frozenset()


def test_each_method_list_still_holds_its_anchor_spellings() -> None:
    """The guard for the test above: two emptied lists are disjoint and would prove nothing."""
    assert ANCHOR_CONSUMING <= CONSUMING_METHODS
    assert ANCHOR_CONFIGURING <= CONFIGURING_METHODS
