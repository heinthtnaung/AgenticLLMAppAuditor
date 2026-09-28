"""Checking a member against the order of the options: a value counts only if both orders give it.

A local model can answer by where an option sits in the list rather than by
what the advisory says. Measured on the pilot's 18 findings
(`measurements/council_eval_runs/order-checked-vulnscout/`), Llama's Attack
Vector, Attack Complexity and User Interaction, and Qwen's Privileges Required
and User Interaction, changed with the order of the list on 7 to 18 of them.
So each member is asked each metric twice, with the options in the
specification's order and reversed, and its two readings become one reply:

- **the same value both ways** -- the reply in the specification's order,
  its quotation and its confidence, quoted or guessed;
- **two different values** -- `MemberOrderSensitive`, which holds both and,
  like a decline, can neither support a value nor contest one;
- **a decline either way** -- a decline;
- **a failure either way** -- that failure, saying which order it came in.

Whichever it is names the member by both prompts it saw: the in-order version,
and the reversed one beside it (`MemberIdentity.reversed_prompt_version`).

The chairman then rules on these replies exactly as on any others. The rule
does not reach a lean towards the middle option, which stays in the middle when
the list is reversed; the measurement flags that separately.
"""

from dataclasses import replace

from council.answer import (
    MemberAnswer,
    MemberFoundNoEvidence,
    MemberGuessed,
    MemberIdentity,
    MemberOrderSensitive,
    MemberReply,
)
from council.run import MemberFailure

REVERSED_ORDER = "with the options reversed"

Reading = MemberReply | MemberFailure


def reconciled(in_order: Reading, reversed_order: Reading) -> Reading:
    """Give one member's reply on one metric from its readings in both orders of the options."""
    refuse_unpaired(in_order, reversed_order)
    both = replace(in_order.member, reversed_prompt_version=reversed_order.member.prompt_version)
    if isinstance(in_order, MemberFailure):
        return replace(in_order, member=both)
    if isinstance(reversed_order, MemberFailure):
        return failed_reversed(reversed_order, both)
    if not named_value(in_order) or not named_value(reversed_order):
        return MemberFoundNoEvidence(metric=in_order.metric, member=both)
    if in_order.value == reversed_order.value:
        return replace(in_order, member=both)
    return MemberOrderSensitive(
        metric=in_order.metric,
        in_order_value=in_order.value,
        reversed_value=reversed_order.value,
        member=both,
    )


def refuse_unpaired(in_order: Reading, reversed_order: Reading) -> None:
    """Refuse two readings that are not one member's on one metric."""
    ahead, behind = asked(in_order), asked(reversed_order)
    if ahead != behind:
        raise ValueError(f"{ahead} cannot be reconciled with {behind}")


def asked(reading: Reading) -> str:
    """Name who gave a reading, and on which metric."""
    return f"{reading.member.name} on {reading.metric}"


def named_value(reply: MemberReply) -> bool:
    """Say whether a reply names a value, quoted or guessed."""
    return isinstance(reply, (MemberAnswer, MemberGuessed))


def failed_reversed(failure: MemberFailure, member: MemberIdentity) -> MemberFailure:
    """Give a failure in the reversed order, saying that is where it happened."""
    return MemberFailure(
        member=member, metric=failure.metric, reason=f"{REVERSED_ORDER}: {failure.reason}"
    )
