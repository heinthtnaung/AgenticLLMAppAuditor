"""The third answer the method gate gives: *this check cannot tell*.

`test_taint_methods.py` holds the two decided answers -- a method that hands its
argument to the model is a finding, a method that configures the object is
silence. This file holds what happens when the method is neither, because a
closed list of consuming methods is only safe if the names it does *not* hold
are said out loud rather than dropped.

That is not hypothetical. The gate first shipped with two answers, so
`agent.generate(question)` -- a consuming method simply absent from the list --
produced no finding *and* no probe: a miss wearing the shape of a clean result,
introduced by the fix for a false positive. The gate now answers
`UNKNOWN_METHOD`, and the trace emits an `INCONCLUSIVE` probe naming the method
it could not judge. Extending the list closes one name; this closes the class.

Every "nothing was reported" case below has a twin over the same snippet that
does report something, so a green result cannot come from a fixture that was
mis-wired in the first place -- `llm.bind(api_key)` and `llm.frobnicate(api_key)`
differ in that one call and nothing else.

Kept apart from `test_taint_methods.py` on purpose: "which methods consume a
value" and "what is said when none of the lists knows the method" are two
questions. Kept apart from `test_taint_defect.py` too -- the unknown method is
decided behaviour now, not a recorded hole; the two shapes that are still silent
live there as strict xfails. And apart from `test_taint_probe_dedupe.py`, which
takes the third question: what the trace does when one source would carry two
probes. Every case below is a single call, so none of them can raise it.
"""

from artifacts.finding import INCONCLUSIVE, SURFACE_SUBJECT
from artifacts.surface import DATA_SOURCE
from checks.taint import CHECK_NAME, LEFT_THE_FILE
from test_taint import FILE, SOURCE_NAME
from test_taint_methods import (
    ENV_SOURCE_NAME, SOURCE_LINE, trace_agent_call, trace_model_config,
    trace_non_surface_call)

# A made-up method name: no real LangChain or LangGraph object has one. What is
# under test is a method *neither* list knows, so inventing the name keeps these
# tests from retiring themselves the day a real one joins `CONSUMING_METHODS`.
UNKNOWN_METHOD = "frobnicate"
UNKNOWN_CALL = f"agent.{UNKNOWN_METHOD}(question)"

# A second invented method, for the one source that reaches two unjudgeable
# calls. Named so it sorts *before* the first one: a dedupe that happened to
# keep the alphabetically smaller name would then be visible as such, rather
# than passing for "the first".
SECOND_UNKNOWN_METHOD = "blorp"
SECOND_UNKNOWN_CALL = f"agent.{SECOND_UNKNOWN_METHOD}(question)"

# The surface the probe must be about: where the untrusted value enters.
SOURCE_ID = f"{FILE}:{SOURCE_LINE}:{DATA_SOURCE}:{SOURCE_NAME}"
ENV_SOURCE_ID = f"{FILE}:{SOURCE_LINE}:{DATA_SOURCE}:{ENV_SOURCE_NAME}"


def test_an_unknown_method_is_not_reported_as_a_finding() -> None:
    """`agent.frobnicate(question)` may consume the value or may not; a finding would claim it does.

    Claiming it is the false positive the method gate exists to prevent.
    """
    findings, _ = trace_agent_call(UNKNOWN_CALL)
    assert findings == []


def test_an_unknown_method_leaves_exactly_one_inconclusive_probe() -> None:
    """The silence the closed list used to answer with, replaced by one record saying so."""
    _, probes = trace_agent_call(UNKNOWN_CALL)
    assert len(probes) == 1
    assert probes[0].outcome == INCONCLUSIVE


def test_the_unknown_method_probe_names_the_method_it_could_not_judge() -> None:
    """Telling a reader *which* call was unjudgeable is the message's whole job."""
    probe = trace_agent_call(UNKNOWN_CALL)[1][0]
    assert f"'{UNKNOWN_METHOD}'" in probe.detail


def test_the_unknown_method_probe_is_about_the_source_surface() -> None:
    """A gap is only useful if it names the surface it is about -- line 1, where the value enters."""
    probe = trace_agent_call(UNKNOWN_CALL)[1][0]
    assert probe.probe_name == CHECK_NAME
    assert (probe.subject_kind, probe.subject_id) == (SURFACE_SUBJECT, SOURCE_ID)


def test_the_unknown_method_probe_gives_the_reason_from_the_vocabulary() -> None:
    """`trace_left_static_analysis` is the schema's word for it, so no schema change was needed."""
    probe = trace_agent_call(UNKNOWN_CALL)[1][0]
    assert probe.reason == LEFT_THE_FILE == "trace_left_static_analysis"


def test_a_configuring_method_leaves_no_probe_either() -> None:
    """`llm.bind(api_key=key)` is silence with nothing inconclusive about it.

    The split between this and the test below is the entire reason the gate has
    three answers rather than two: an unknown method is not evidence of
    configuration, and filing it as configuration is how a closed list becomes
    a silent stop.
    """
    assert trace_model_config("llm.bind(api_key=api_key)") == ([], [])


def test_an_unknown_method_on_the_same_bound_model_is_probed() -> None:
    """The twin of the test above: same source, same receiver, a method neither list knows."""
    findings, probes = trace_model_config(f"llm.{UNKNOWN_METHOD}(api_key)")
    assert findings == []
    assert [(p.outcome, p.subject_id) for p in probes] == [(INCONCLUSIVE, ENV_SOURCE_ID)]


def test_an_untainted_name_at_an_unknown_method_is_not_probed() -> None:
    """A tainted value reaching an unjudgeable method is the probe, not the method alone.

    `sanitiser` is a name this file bound to no source, so nothing is in doubt.
    """
    assert trace_non_surface_call(f"agent.{UNKNOWN_METHOD}(sanitiser)") == ([], [])


def test_a_literal_at_an_unknown_method_is_not_probed() -> None:
    """Nothing untrusted is passed, so there is nothing whose fate is in doubt."""
    assert trace_agent_call(f'agent.{UNKNOWN_METHOD}("hardcoded")') == ([], [])


def test_an_unknown_method_on_a_receiver_that_is_no_surface_is_not_probed() -> None:
    """`logger.frobnicate(question)` is not a model or a tool; the receiver gate still runs first."""
    assert trace_non_surface_call(f"logger.{UNKNOWN_METHOD}(question)") == ([], [])
