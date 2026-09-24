"""What one council did over one advisory: every round, who was asked, and who was not.

`council.runner` makes a run and `cli.council_detail` reads one, so the record
lives apart from the dispatch that fills it. A run reads metric by metric, and
each round holds its replies in roster order, whatever order the calls were
made in.
"""

from dataclasses import dataclass
from itertools import chain

from council.answer import MemberIdentity, MemberReply
from council.roster import SkippedMember
from council.ruling import MetricRuling


@dataclass(frozen=True)
class MemberFailure:
    """A member that was asked one metric and gave back nothing usable, and why.

    Not a member that was never asked -- those are `CouncilRun.skipped`, and the
    two are different facts about a run. This one was reached and its call
    failed, or it replied and the reply could not be read. It names the member as
    a reply does, because a failure is the call an auditor most needs to trace.
    """

    member: MemberIdentity
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
        return tuple(chain.from_iterable(round_.failures for round_ in self.rounds))
