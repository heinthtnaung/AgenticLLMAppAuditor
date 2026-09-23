"""Putting one advisory to the roster, metric by metric, and collecting the rulings.

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
"""

from dataclasses import dataclass
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
from council.roster import Member, Roster, SkippedMember, members_to_ask
from council.ruling import Fallback, MetricRuling
from council.transport import ModelUnavailable


@dataclass(frozen=True)
class MemberFailure:
    """A member that was asked one metric and gave back nothing usable, and why.

    Not a member that was never asked -- those are `CouncilRun.skipped`, and the
    two are different facts about a run. This one was reached and its call
    failed, or it replied and the reply could not be read.
    """

    member_name: str
    metric: str
    reason: str


@dataclass(frozen=True)
class MetricRound:
    """One metric put to every reachable member: what came back, and the ruling on it."""

    metric: str
    replies: tuple[MemberReply, ...]
    failures: tuple[MemberFailure, ...]
    ruling: MetricRuling


@dataclass(frozen=True)
class CouncilRun:
    """One council over one advisory: every round, who was asked, and who was not.

    `skipped` is the members never asked, by `egress` or by having no client.
    `failures` is the calls that were made and gave nothing usable back. They are
    different facts about a run and a report should not merge them.
    """

    rounds: tuple[MetricRound, ...]
    asked: tuple[str, ...]
    skipped: tuple[SkippedMember, ...]
    single_assessor: bool

    @property
    def rulings(self) -> dict[str, MetricRuling]:
        """The rulings by metric, in the shape `chairman.agreed_vector` takes."""
        return {round_.metric: round_.ruling for round_ in self.rounds}

    @property
    def failures(self) -> tuple[MemberFailure, ...]:
        """Every call that was made and gave back nothing usable, across every metric."""
        return tuple(failure for round_ in self.rounds for failure in round_.failures)


def nobody_asking(metric: str, member: str) -> None:
    """Report nothing, which is what a run nobody is watching needs."""


def assess(
    advisory_text: str,
    roster: Roster,
    fallbacks: Mapping[str, Fallback],
    clients: Mapping[str, AskMember] = PROVIDER_CLIENTS,
    asking: Callable[[str, str], None] = nobody_asking,
) -> CouncilRun:
    """Put one advisory to the roster, one metric at a time, and collect the rulings."""
    refuse_incomplete_fallbacks(fallbacks)
    reachable = reachable_members(members_to_ask(roster), clients)
    rounds = [
        assess_metric(metric, advisory_text, reachable, clients, fallbacks[metric], asking)
        for metric in METRIC_ORDER
    ]
    return CouncilRun(
        rounds=tuple(rounds),
        asked=tuple(member.name for member in reachable),
        skipped=unreachable_members(roster, clients),
        # Counted from who was actually asked: a roster of three that reaches one
        # cross-checks nothing, whatever the operator configured.
        single_assessor=len(reachable) == 1,
    )


def assess_metric(
    metric: str,
    advisory_text: str,
    members: tuple[Member, ...],
    clients: Mapping[str, AskMember],
    fallback: Fallback,
    asking: Callable[[str, str], None] = nobody_asking,
) -> MetricRound:
    """Ask every reachable member about one metric and rule on what came back."""
    prompt = build_prompt(metric, advisory_text)
    outcomes = [ask_one_member(member, prompt, clients, asking) for member in members]
    replies = tuple(item for item in outcomes if not isinstance(item, MemberFailure))
    return MetricRound(
        metric=metric,
        replies=replies,
        failures=tuple(item for item in outcomes if isinstance(item, MemberFailure)),
        # The redacted text, never `advisory_text`: this is the whole reason the
        # runner builds the prompt rather than taking one.
        ruling=rule_on_metric(metric, replies, prompt.advisory_shown, fallback),
    )


def ask_one_member(
    member: Member,
    prompt: MemberPrompt,
    clients: Mapping[str, AskMember],
    asking: Callable[[str, str], None] = nobody_asking,
) -> MemberReply | MemberFailure:
    """Put one prompt to one member, recording a failure rather than ending the run."""
    # Said before the call, so a member that takes half a minute is a line that
    # sits there rather than a number nobody has yet.
    asking(prompt.metric, member.name)
    try:
        said = clients[member.provider](member, prompt)
        return read_reply(said, prompt.metric, member.identify(prompt.version))
    # ModelUnavailable is the server; ValueError covers both a reply that cannot
    # be read and one naming a value the metric forbids.
    except (ModelUnavailable, ValueError) as fault:
        return MemberFailure(member_name=member.name, metric=prompt.metric, reason=str(fault))


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
