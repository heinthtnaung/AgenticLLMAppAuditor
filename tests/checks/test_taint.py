"""LLM01: an untrusted value traced from where it enters to where a model consumes it.

The mechanism is three lines long -- a source bound to a name, a sink bound to
a name, and a call handing one to the other -- so most of these tests are about
where it stops: a source that reaches nothing, a sink that is not a model, and
the source the file never named, which is reported as inconclusive rather than
dropped. "We could not look" and "we looked and found nothing" are different
answers, and the probe record is what keeps them apart.

The last two hold the other boundary: a scope. A source in one function and a
sink call in another that reuses the name are not a trace, and reporting one
was a real regression.
"""

import ast

from artifacts.finding import INCONCLUSIVE, STATIC, SURFACE_SUBJECT
from artifacts.surface import AGENT_DEF, DATA_SOURCE, PROMPT_TEMPLATE, TOOL_CALL, Surface
from checks.taint import CHECK_NAME, LEFT_THE_FILE, OWASP_ID, trace_file
from parsing.languages import PYTHON

FILE = "main.py"
OTHER_FILE = "other.py"

SOURCE_NAME = "st.chat_input"
AGENT_NAME = "AgentExecutor.from_agent_and_tools"
TOOL_NAME = "GetUserTransactions"

# The corpus app's trace, reduced to the three lines that carry it: the walrus
# that names the untrusted value, the agent bound to a name, and the call that
# hands one to the other.
TRACED = '''if prompt := st.chat_input("ask"):
    executor = AgentExecutor.from_agent_and_tools(tools=tools)
    response = executor(prompt, callbacks=[])
'''

# The same source and sink, with nothing passed between them.
NEVER_PASSED = '''prompt = st.chat_input("ask")
executor = AgentExecutor.from_agent_and_tools(tools=tools)
response = executor("hardcoded")
'''

# A source whose value the file never binds to a name.
UNBOUND = 'st.chat_input("ask")\n'

# The same source and sink, one function deep: the positive twin of the case
# below, without which "no finding" could equally mean the trace found nothing.
ONE_FUNCTION = '''def handle():
    prompt = st.chat_input("ask")
    executor = AgentExecutor.from_agent_and_tools(tools=tools)
    executor(prompt)
'''

# Two functions reusing the names `prompt` and `executor`. Only the second one
# calls the agent, and the value it hands over came from a sanitiser, not from
# the chat input -- so there is nothing here to report.
CROSS_SCOPE = '''def takes_input():
    prompt = st.chat_input("ask")
    executor = AgentExecutor.from_agent_and_tools(tools=tools)

def answers():
    prompt = sanitise()
    executor = AgentExecutor.from_agent_and_tools(tools=tools)
    executor(prompt)
'''


def surface(kind: str, name: str, line: int, file: str = FILE) -> Surface:
    """Build one surface at a line, as the extractor would have reported it."""
    return Surface(kind, name, file, line, PYTHON, "detected by test")


def trace(source: str, surfaces: list) -> tuple:
    """Run the trace over a snippet and the surfaces the extractor found in it."""
    return trace_file(ast.parse(source), FILE, surfaces)


def traced_walrus() -> tuple:
    """Trace the three-line source-to-sink snippet."""
    return trace(TRACED, [surface(DATA_SOURCE, SOURCE_NAME, 1),
                          surface(AGENT_DEF, AGENT_NAME, 2)])


def test_a_source_reaching_an_agent_is_reported() -> None:
    """The whole mechanism: chat input taints a name, and that name reaches the agent."""
    findings, _ = traced_walrus()
    assert len(findings) == 1
    assert findings[0].rule_id == CHECK_NAME


def test_the_finding_is_anchored_on_the_source_not_the_sink() -> None:
    """Line 1, where the value enters -- that is where the grading key records it."""
    findings, _ = traced_walrus()
    assert (findings[0].file, findings[0].line) == (FILE, 1)


def test_the_finding_cites_the_source_surface_whole() -> None:
    """The surface is copied in full, so no later phase has to parse the id."""
    finding = traced_walrus()[0][0]
    assert finding.surface_id == f"{FILE}:1:{DATA_SOURCE}:{SOURCE_NAME}"
    assert (finding.surface_kind, finding.surface_name) == (DATA_SOURCE, SOURCE_NAME)


def test_the_finding_is_llm01_and_static() -> None:
    """Nothing was executed to reach it, and the record says so."""
    finding = traced_walrus()[0][0]
    assert finding.owasp_id == OWASP_ID == "LLM01"
    assert finding.detection == STATIC and finding.probe_id is None


def test_a_followed_source_leaves_no_probe() -> None:
    """The trace reached a conclusion, so there is no gap to report."""
    assert traced_walrus()[1] == []


def test_a_source_never_passed_to_a_sink_is_not_reported() -> None:
    """The value was named and followed; it simply never reached the model."""
    findings, probes = trace(NEVER_PASSED, [surface(DATA_SOURCE, SOURCE_NAME, 1),
                                            surface(AGENT_DEF, AGENT_NAME, 2)])
    assert findings == []
    assert probes == []


def test_an_unbound_source_is_reported_as_inconclusive() -> None:
    """The value was never named, so the trace could not follow it -- and says so."""
    findings, probes = trace(UNBOUND, [surface(DATA_SOURCE, SOURCE_NAME, 1)])
    assert findings == []
    assert len(probes) == 1
    assert probes[0].outcome == INCONCLUSIVE


def test_the_inconclusive_probe_names_what_it_could_not_follow() -> None:
    """A gap is only useful if it says which surface it is about."""
    probe = trace(UNBOUND, [surface(DATA_SOURCE, SOURCE_NAME, 1)])[1][0]
    assert probe.probe_name == CHECK_NAME
    assert (probe.subject_kind, probe.subject_id) == (
        SURFACE_SUBJECT, f"{FILE}:1:{DATA_SOURCE}:{SOURCE_NAME}")


def test_the_inconclusive_probe_gives_the_reason_from_the_vocabulary() -> None:
    """`trace_left_static_analysis` is the schema's word for it, not free text."""
    probe = trace(UNBOUND, [surface(DATA_SOURCE, SOURCE_NAME, 1)])[1][0]
    assert probe.reason == LEFT_THE_FILE == "trace_left_static_analysis"


def test_a_tool_call_is_a_sink_too() -> None:
    """A tool the model drives consumes the value just as the agent does."""
    source = 'prompt = st.chat_input("ask")\ntool = GetUserTransactions()\ntool(prompt)\n'
    findings, _ = trace(source, [surface(DATA_SOURCE, SOURCE_NAME, 1),
                                 surface(TOOL_CALL, TOOL_NAME, 2)])
    assert [f.line for f in findings] == [1]


def test_a_prompt_template_is_not_a_sink() -> None:
    """Only a model or a model-driven tool consuming the value is this finding."""
    source = 'prompt = st.chat_input("ask")\ntemplate = PromptTemplate()\ntemplate(prompt)\n'
    findings, _ = trace(source, [surface(DATA_SOURCE, SOURCE_NAME, 1),
                                 surface(PROMPT_TEMPLATE, "PromptTemplate", 2)])
    assert findings == []


def test_a_keyword_argument_carries_the_taint() -> None:
    """Handing the value over by keyword is the same hand-over."""
    source = ('prompt = st.chat_input("ask")\n'
              'executor = AgentExecutor.from_agent_and_tools()\n'
              'executor(input=prompt)\n')
    findings, _ = trace(source, [surface(DATA_SOURCE, SOURCE_NAME, 1),
                                 surface(AGENT_DEF, AGENT_NAME, 2)])
    assert [f.line for f in findings] == [1]


def test_a_surface_in_another_file_is_not_traced() -> None:
    """The trace is one file wide, and a surface from elsewhere must not leak into it."""
    surfaces = [surface(DATA_SOURCE, SOURCE_NAME, 1, file=OTHER_FILE),
                surface(AGENT_DEF, AGENT_NAME, 2)]
    assert trace(TRACED, surfaces) == ([], [])


def test_a_file_with_no_surfaces_yields_nothing() -> None:
    """Nothing to trace is a clean result, not an error."""
    assert trace(TRACED, []) == ([], [])


def test_a_source_reaching_two_sinks_is_reported_once() -> None:
    """One untrusted value is one finding: it is anchored on the source, not the sink.

    Reported twice, the two records share a surface id and a rule, so they share
    a finding id -- and `build_findings_document` rejects the document outright.
    """
    source = ('prompt = st.chat_input("ask")\n'
              'first = AgentExecutor.from_agent_and_tools()\n'
              'second = AgentExecutor.from_agent_and_tools()\n'
              'first(prompt)\n'
              'second(prompt)\n')
    findings, _ = trace(source, [surface(DATA_SOURCE, SOURCE_NAME, 1),
                                 surface(AGENT_DEF, AGENT_NAME, 2),
                                 surface(AGENT_DEF, AGENT_NAME, 3)])
    assert len({finding.id for finding in findings}) == len(findings)


def test_a_source_and_a_sink_inside_one_function_are_reported() -> None:
    """The trace has to work in a function body, or the isolation test below proves nothing."""
    findings, _ = trace(ONE_FUNCTION, [surface(DATA_SOURCE, SOURCE_NAME, 2),
                                       surface(AGENT_DEF, AGENT_NAME, 3)])
    assert [f.line for f in findings] == [2]


def test_a_source_in_one_function_is_not_matched_to_a_sink_call_in_another() -> None:
    """The name is reused, but the untrusted value never leaves the function that took it."""
    surfaces = [surface(DATA_SOURCE, SOURCE_NAME, 2),
                surface(AGENT_DEF, AGENT_NAME, 3),
                surface(AGENT_DEF, AGENT_NAME, 7)]
    assert trace(CROSS_SCOPE, surfaces) == ([], [])
