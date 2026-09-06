"""A value handed to the model inside a container is still handed to the model.

`argument_names` read bare names only, so `agent.invoke({"input": question})` --
the standard LangChain spelling -- passed the untrusted value over invisibly:
no finding, and no probe either, because `question` *was* bound and the method
*was* `invoke`, so neither gap the check reports applied. The audit read as
"traced, found nothing".

A literal container and an f-string carry their contents to the callee
unchanged, so `bindings.TRANSPARENT_WRAPPERS` is now looked through, and this
file pins the wrapped shapes end to end through `trace_file`. Two of them live
next door instead: the dict literal itself and the nested list of chat messages
are in `test_taint_methods.py`, where the shape that retired the strict xfail
was recorded.

A **call** is not a wrapper. `agent.invoke(build(question))` hands over whatever
`build` returned, and that shape is still followed by nothing and reported by
nothing -- an open defect, held as a strict xfail in `test_taint_defect.py` and
deliberately not restated here as if it were decided.

Every case is the same three-line flow with one call changed, so the wrapping is
the only thing under test. `tests/parsing/test_argument_wrappers.py` is the same
question one level down, against `argument_names` itself.
"""

from test_taint import FILE
from test_taint_methods import trace_agent_call

# Where the untrusted value enters, in every snippet below.
SOURCE_LINE = 1

# One wrapping per line, each holding the tainted name `question`. The label is
# what a failure names, so a broken wrapper is read off the report directly.
WRAPPED_CALLS = {
    "a list": "agent.invoke([question])",
    "a tuple": "agent.invoke((question,))",
    "a set": "agent.invoke({question})",
    "an f-string": 'agent.invoke(f"Answer this: {question}")',
    "a starred list": "agent.invoke(*[question])",
    "a double-starred dict": 'agent.invoke(**{"input": question})',
}

# The same wrapping with nothing tainted inside it: the twin of the list case
# above, and the guard that the container is not what taints the call.
ONLY_LITERALS = 'agent.invoke(["what are your hours?", 42])'


def reported_by(call: str) -> list[tuple[str, int]]:
    """Where the trace anchors each finding for one call on the bound agent."""
    findings, _probes = trace_agent_call(call)
    return [(finding.file, finding.line) for finding in findings]


def test_every_literal_wrapper_still_reaches_the_model() -> None:
    """Six spellings of the same hand-over, each anchored on the source that entered."""
    assert {label: reported_by(call) for label, call in WRAPPED_CALLS.items()} == \
        {label: [(FILE, SOURCE_LINE)] for label in WRAPPED_CALLS}


def test_a_wrapped_value_leaves_no_probe_behind() -> None:
    """The trace reached a conclusion about the f-string, so there is no gap to report."""
    _findings, probes = trace_agent_call(WRAPPED_CALLS["an f-string"])
    assert probes == []


def test_a_container_holding_only_literals_is_not_reported() -> None:
    """Looking through a container must not make every container call a finding."""
    assert reported_by(ONLY_LITERALS) == []
