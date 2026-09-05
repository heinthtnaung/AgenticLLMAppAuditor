"""One subject, one probe: what the dedupe drops and what it must not.

The unknown-method gate next door answers a single call. This file answers the
question that only appears once a file has *two* calls the gate cannot judge, or
two sources: a `Probe` is keyed by its subject, so two probes about one source
would share a `probe_id` and the trace has to drop one. Which one it drops, and
which ones it leaves alone, is decided behaviour rather than an accident, so it
is pinned here.

Three rules are under test:

* a source that is already reported as a finding carries no probe beside it --
  it was followed, so nothing about it is inconclusive;
* the drop is per source, not per file: a *second* source that reached only an
  unjudgeable method keeps its own probe;
* of two probes on one source, the kept one is the one `ast.walk` meets first.

Split from `test_taint_unknown_method.py` because it asks a different question.
That file certifies the gate's third answer over one call; these four certify
how the trace collapses several answers about one subject, and they need their
own two-call and two-source snippets to do it. Neither `UNKNOWN_METHOD` nor
anything else is redefined -- it is imported, so the two files cannot drift.
"""

from artifacts.finding import INCONCLUSIVE
from artifacts.surface import AGENT_DEF, DATA_SOURCE
from test_taint import AGENT_NAME, FILE, SOURCE_NAME, surface, trace
from test_taint_methods import SOURCE_LINE
from test_taint_unknown_method import (
    SECOND_UNKNOWN_CALL, SECOND_UNKNOWN_METHOD, SOURCE_ID, UNKNOWN_CALL,
    UNKNOWN_METHOD)

# One untrusted value and one bound agent, handed to two calls that vary. The
# dedupe -- a source reported as a finding carries no probe beside it -- needs
# both calls in one file, which the single-call snippets next door cannot give.
TWO_CALLS = ('question = st.chat_input("ask")\n'
             'agent = AgentExecutor.from_agent_and_tools(tools=tools)\n'
             'first = {first}\n'
             'second = {second}\n')

# Two untrusted values on one agent: the first is followed to a consuming
# method, the second only to an unknown one. The guard that the dedupe drops the
# probe belonging to a reported source and not every probe in the file.
TWO_SOURCES = ('question = st.chat_input("ask")\n'
               'uploaded = st.file_uploader("file")\n'
               'agent = AgentExecutor.from_agent_and_tools(tools=tools)\n'
               'agent.invoke(question)\n'
               f'agent.{UNKNOWN_METHOD}(uploaded)\n')

UPLOAD_SOURCE_NAME = "st.file_uploader"
UPLOAD_SOURCE_LINE = 2
UPLOAD_SOURCE_ID = f"{FILE}:{UPLOAD_SOURCE_LINE}:{DATA_SOURCE}:{UPLOAD_SOURCE_NAME}"


def trace_two_calls(first: str, second: str) -> tuple:
    """Trace one untrusted value handed to two calls on the same bound agent."""
    return trace(TWO_CALLS.format(first=first, second=second),
                 [surface(DATA_SOURCE, SOURCE_NAME, SOURCE_LINE),
                  surface(AGENT_DEF, AGENT_NAME, 2)])


def trace_two_sources() -> tuple:
    """Trace two untrusted values, one reaching a consuming method and one an unknown method."""
    return trace(TWO_SOURCES,
                 [surface(DATA_SOURCE, SOURCE_NAME, SOURCE_LINE),
                  surface(DATA_SOURCE, UPLOAD_SOURCE_NAME, UPLOAD_SOURCE_LINE),
                  surface(AGENT_DEF, AGENT_NAME, 3)])


def test_a_source_reaching_both_kinds_of_method_is_reported_as_a_finding() -> None:
    """The value is known to reach the model, so the unknown call adds no doubt to it."""
    findings, probes = trace_two_calls("agent.invoke(question)", UNKNOWN_CALL)
    assert [(f.file, f.line) for f in findings] == [(FILE, SOURCE_LINE)]
    assert probes == []


def test_the_dedupe_holds_when_the_unknown_call_comes_first() -> None:
    """Same two calls in the other order: which one the walk meets first must not decide the answer."""
    findings, probes = trace_two_calls(UNKNOWN_CALL, "agent.invoke(question)")
    assert [(f.file, f.line) for f in findings] == [(FILE, SOURCE_LINE)]
    assert probes == []


def test_a_second_source_at_an_unknown_method_keeps_its_probe() -> None:
    """The guard for the two above: the dedupe drops one source's probe, not the file's.

    Without this, "no probes" in the two dedupe tests could equally mean the
    check stopped emitting them.
    """
    findings, probes = trace_two_sources()
    assert [f.surface_id for f in findings] == [SOURCE_ID]
    assert [(p.outcome, p.subject_id) for p in probes] == [(INCONCLUSIVE, UPLOAD_SOURCE_ID)]


def test_a_source_at_two_unknown_methods_keeps_only_the_first_probe() -> None:
    """One source, two unjudgeable methods, one probe -- and it names `frobnicate`.

    Two probes on one subject would share a `probe_id`, so one of them has to be
    dropped. *Which* one is arbitrary: neither method is the better example, and
    the trace could as defensibly keep the last. It is pinned because the
    artifact exposes the choice through `detail`, so leaving it unpinned lets the
    text of a published probe change without a single test going red.
    """
    findings, probes = trace_two_calls(UNKNOWN_CALL, SECOND_UNKNOWN_CALL)
    assert findings == []
    assert [(p.outcome, p.subject_id) for p in probes] == [(INCONCLUSIVE, SOURCE_ID)]
    assert f"'{UNKNOWN_METHOD}'" in probes[0].detail
    assert SECOND_UNKNOWN_METHOD not in probes[0].detail


def test_the_kept_probe_is_the_one_the_walk_meets_first() -> None:
    """The same two methods swapped: `blorp` first is the one kept.

    "First" is the trace's own order -- statements in source order, then
    `ast.walk` inside each -- which equals source order only for calls at the
    same nesting depth. Here the two calls are separate statements, so it does.
    It is *not* file order in general: put both in one statement and nest the
    earlier one, as in `out = wrap(agent.blorp(q)) + agent.frobnicate(q)`, and
    the kept probe names `frobnicate` even though `blorp` is written first,
    because `ast.walk` reaches the shallower call sooner. That shape is left
    unpinned deliberately -- it falls out of walk order rather than out of a
    decision anyone made, and pinning it would freeze an artefact as a contract.
    """
    _, probes = trace_two_calls(SECOND_UNKNOWN_CALL, UNKNOWN_CALL)
    assert len(probes) == 1
    assert f"'{SECOND_UNKNOWN_METHOD}'" in probes[0].detail
    assert UNKNOWN_METHOD not in probes[0].detail
