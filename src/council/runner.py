"""Putting one advisory to the roster, member by member, and collecting the rulings.

**This dispatches; it does not decide.** No reconciliation happens here -- that
is `chairman.rule_on_metric` -- and no number appears anywhere, because the
council hands over a vector and the engine turns vectors into scores.

Two things it is responsible for getting right, and both are refusals rather
than conventions:

- **A member is only ever shown the redacted advisory.** The runner builds the
  prompt, and `prompt.advisory_shown` is what both the member and the quotation
  check are given. Handing the chairman the raw text would fail every quotation
  spanning a redaction and report the metric as an absence the advisory never
  had; `evidence.refuse_unredacted` exists to catch exactly this caller.
- **A member nothing can reach does not quietly vanish.** Who can be reached,
  and the client that reaches them, is `council.providers`; what this file
  guarantees is that everyone it could not ask is on the record. A record that
  omits a member is not a record.

A member whose call fails, or whose reply cannot be read, costs that one metric
and not the run: the failure is recorded and the remaining members are still
asked. Losing a whole assessment because one model timed out would be the worse
answer.

**One member answers every metric before the next member is asked.** Local
members share one Ollama server, and two that do not fit in its memory together
are swapped whenever the member changes -- a model reload, many times slower
than a call to a model already loaded. Asked metric by metric, the member would
change on every call; asked member by member, it changes once per member per
advisory. The order decides only when a call is made: no member is shown
another's answer, and a metric is ruled on once every reply to it is in, so
neither independence nor reconciliation depends on it. Roster order still
decides who is asked first, which is the cost order the escalation reasoning
below relies on.

Call order is a difference the reproducibility analysis in
`measurements/README.md` does not rule out, and the runs recorded in
`measurements/council_runs/` were asked metric by metric. A run asked in this
order is a new baseline, not a replication of those.

**Every reachable member is asked every metric**, which is the ask-all policy
`docs/COUNCIL.md` names beside escalation. Escalation -- ask the cheapest first,
send only a contested or unresolved metric to a costlier member -- is a dispatch
change and would be made here.

That trigger has a precondition: **a cheap tier of two or more members that can
contest something between themselves.** A contest requires two distinct
*verified* values (`ruling.ContestedMetric`), so one member asked alone can only
settle or leave unresolved. On a roster of one cheap member and one costly one,
every metric the cheap member settles alone is agreement nobody cross-checked.
Measured on a two-member roster (`measurements/council_runs/`): 61 of 144 metrics
came out contested because the second member disagreed, and this trigger would
have recorded all 61 as settled. `single_assessor` counts the members reached,
not the members asked about a given metric, so it would not say so; the `SOLE`
basis on each metric settled by one member's quotation alone would.

That holds for a trigger on what members reply, not for escalation in general. A
trigger on the finding's `disputed_metrics()` -- which `cli.council_run` already
reads to scope a run, and which no member's reply changes -- reaches the costly
member even from a one-member cheap tier. That is a different policy, and
`docs/COUNCIL.md` names it as one.
"""

from typing import Callable, Mapping

from cvss.metrics import METRIC_ORDER
from council.answer import MemberReply
from council.chairman import rule_on_metric
from council.prompt import MemberPrompt, build_prompt
from council.providers import (
    PROVIDER_CLIENTS,
    AskMember,
    reachable_members,
    unreachable_members,
)
from council.reply import read_reply
from council.roster import Member, Roster, members_to_ask
from council.ruling import Fallback
from council.run import CouncilRun, MemberFailure, MetricRound
from council.transport import ModelUnavailable

# What one call to one member gave back.
CallOutcome = MemberReply | MemberFailure


def nobody_asking(metric: str, member: str) -> None:
    """Report nothing, which is what a run nobody is watching needs."""


def assess(
    advisory_text: str,
    roster: Roster,
    fallbacks: Mapping[str, Fallback],
    clients: Mapping[str, AskMember] = PROVIDER_CLIENTS,
    asking: Callable[[str, str], None] = nobody_asking,
) -> CouncilRun:
    """Put one advisory to the roster, one member at a time, and rule on every metric."""
    refuse_incomplete_fallbacks(fallbacks)
    reachable = reachable_members(members_to_ask(roster), clients)
    prompts = tuple(build_prompt(metric, advisory_text) for metric in METRIC_ORDER)
    answered = [ask_every_metric(member, prompts, clients, asking) for member in reachable]
    rounds = [rule_on_round(prompt, answered, fallbacks[prompt.metric]) for prompt in prompts]
    return CouncilRun(
        rounds=tuple(rounds),
        asked=tuple(member.name for member in reachable),
        skipped=unreachable_members(roster, clients),
        # Counted from who was actually asked: a roster of three that reaches one
        # cross-checks nothing, whatever the operator configured.
        single_assessor=len(reachable) == 1,
    )


def ask_every_metric(
    member: Member,
    prompts: tuple[MemberPrompt, ...],
    clients: Mapping[str, AskMember],
    asking: Callable[[str, str], None] = nobody_asking,
) -> dict[str, CallOutcome]:
    """Put every metric's prompt to one member, and give what came back by metric."""
    return {prompt.metric: ask_one_member(member, prompt, clients, asking) for prompt in prompts}


def rule_on_round(
    prompt: MemberPrompt, answered: list[dict[str, CallOutcome]], fallback: Fallback
) -> MetricRound:
    """Gather every member's outcome on one metric, in roster order, and rule on it."""
    outcomes = [by_metric[prompt.metric] for by_metric in answered]
    replies = tuple(item for item in outcomes if not isinstance(item, MemberFailure))
    return MetricRound(
        metric=prompt.metric,
        replies=replies,
        failures=tuple(item for item in outcomes if isinstance(item, MemberFailure)),
        # The redacted text, never the raw advisory: this is the whole reason the
        # runner builds the prompt rather than taking one.
        ruling=rule_on_metric(prompt.metric, replies, prompt.advisory_shown, fallback),
    )


def ask_one_member(
    member: Member,
    prompt: MemberPrompt,
    clients: Mapping[str, AskMember],
    asking: Callable[[str, str], None] = nobody_asking,
) -> CallOutcome:
    """Put one prompt to one member, recording a failure rather than ending the run."""
    # Said before the call, so a member that takes half a minute is a line that
    # sits there rather than a number nobody has yet.
    asking(prompt.metric, member.name)
    who = member.identify(prompt.version)
    try:
        said = clients[member.provider](member, prompt)
        return read_reply(said, prompt.metric, who)
    # ModelUnavailable is the server; ValueError covers both a reply that cannot
    # be read and one naming a value the metric forbids.
    except (ModelUnavailable, ValueError) as fault:
        return MemberFailure(member=who, metric=prompt.metric, reason=str(fault))


def refuse_incomplete_fallbacks(fallbacks: Mapping[str, Fallback]) -> None:
    """Refuse a run without a fallback ready for every metric, before any model is asked."""
    # Which published source a fallback comes from is the caller's to decide:
    # nothing here may privilege a source, and the design has settled no rule.
    if not isinstance(fallbacks, Mapping):
        raise TypeError(
            f"Fallbacks must be a mapping of metric to fallback, "
            f"not {type(fallbacks).__name__}"
        )
    missing = [metric for metric in METRIC_ORDER if metric not in fallbacks]
    if missing:
        raise ValueError(f"No fallback ready for {', '.join(missing)}; supply one for each metric")
