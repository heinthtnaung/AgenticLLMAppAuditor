"""The executable record of what the taint trace still cannot follow, as strict xfails.

The original entry here -- `agent.invoke(question)`, unseen because
`bindings.called_name` answered `""` for any attribute callee -- is **fixed**.
`called_name` was replaced by `receiver_name` and `method_name`, and the flow is
now reported; its test lives with the rest of the decided behaviour in
`test_taint_methods.py`. Two shapes are still unfollowable, and they fail the
same way the fixed one did:

* a deeper chain, `agent.runnable.invoke(question)` -- the receiver is the
  *value* of `agent.runnable`, which this file never bound to a name;
* a value through a nested call, `agent.invoke(build(question))` --
  `argument_names` looks through literal containers now, but not through a
  call, whose return value is not what was passed in.

The container shape that used to sit here -- `agent.invoke({"input": question})`
-- is **fixed**, and its test moved to `test_taint_methods.py` with the rest of
the decided behaviour. That is the retirement path this file describes.

Both yield **no finding and no probe**, and neither of the two probes the check
does emit catches them: `_unfollowed` reports only a source that was never bound
to a name, and in both snippets `question` was bound; the unknown-method probe
reports only a method neither list knows, and in both snippets the method is
`invoke`. So the audit reads as *traced and found nothing* where the truth is
*could not follow*, which is the distinction `taint.py`'s docstring, the probe
vocabulary and rule 8 all exist to preserve. A silent miss in a security tool is
worse than a loud gap.

Every test here is `xfail(strict=True)`: each states what the trace should do,
fails today because it does not, and the day someone fixes it the suite goes red
on the unexpected pass and `docs/TODO.md` has to be closed. That is exactly how
the `agent.invoke` entry above retired. A defect recorded this way cannot rot
quietly.

Separate from `test_taint.py`, `test_taint_methods.py` and
`test_taint_unknown_method.py`, which certify what the check really does. The two
kinds must not be mixed: a reader scanning those files for the trace's boundaries
would otherwise read a known hole as a decided one. These two are the *only*
silent stops left -- the unknown method used to be a third and is now loud.
"""

import pytest

from test_taint_methods import trace_agent_call

# The remaining blind shapes, quoted for whoever meets them as a test failure
# rather than as prose in docs/TODO.md. The pointer names the file and what to
# search for, never a heading: the previous reason quoted an exact title, that
# title was rewritten, and the reader chasing a strict-xfail failure was sent to
# a section that no longer existed. "The LLM01 entry" survives the next rewrite.
DEEP_CHAIN_UNRESOLVED = (
    "open defect, see the LLM01 entry in docs/TODO.md -- the deep chain: "
    "bindings.receiver_name answers '' for a.b.c(x), so "
    "agent.runnable.invoke(question) matches no bound sink, and the miss is "
    "not reported as an INCONCLUSIVE probe either")

NESTED_CALL_UNRESOLVED = (
    "open defect, see the LLM01 entry in docs/TODO.md -- the nested call: "
    "argument_names looks through literal containers but not through a call, so "
    "agent.invoke(build(question)) hands the value over invisibly, and the miss "
    "is not reported as an INCONCLUSIVE probe either")


@pytest.mark.xfail(strict=True, reason=DEEP_CHAIN_UNRESOLVED)
def test_a_sink_reached_through_a_deeper_chain_is_not_answered_with_silence() -> None:
    """Report the flow or report the gap: an empty answer is the one wrong result.

    Written as "a finding or a probe" rather than "an INCONCLUSIVE probe" on
    purpose. Either fix retires it -- the honesty half by emitting the probe,
    the capability half by resolving the chain and reporting the flow -- whereas
    a test demanding a probe specifically would keep failing after the
    capability half landed, and say something untrue while doing it.
    """
    findings, probes = trace_agent_call("agent.runnable.invoke(question)")
    assert findings or probes


@pytest.mark.xfail(strict=True, reason=NESTED_CALL_UNRESOLVED)
def test_a_value_handed_through_a_nested_call_is_not_answered_with_silence() -> None:
    """The hole `argument_names` left when it learned to look through containers.

    A literal container carries its contents to the callee unchanged, so walking
    one is sound. A call does not: `build(question)` returns whatever `build`
    made of it. Naming that `question` would be a different claim -- so it is
    not walked, and the shape is recorded here rather than passing as silence.
    """
    findings, probes = trace_agent_call("agent.invoke(build(question))")
    assert findings or probes
