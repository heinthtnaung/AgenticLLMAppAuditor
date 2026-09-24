"""Guards on the order the runner asks in: roster first, member by member, each call announced.

The record does not follow the calls: a run still reads metric by metric, with
each round's replies in roster order.
"""

from itertools import product

from council.roster import Roster
from council.run import MetricRound
from council.runner import assess
from cvss.metrics import METRIC_ORDER
from council_samples import FALLBACKS, RAW_ADVISORY, clients_of, member, replying

PAIR = ("one", "two")


def calls_made() -> list[tuple[str, str, str]]:
    """Run a council of two, noting each announcement and each call as it happens."""
    said = []

    def announcing(member_asked, prompt):
        """Note that a member was asked, then answer it."""
        said.append(("asked", prompt.metric, member_asked.name))
        return replying()(member_asked, prompt)

    roster = Roster(tuple(member(name) for name in PAIR))
    assess(RAW_ADVISORY, roster, FALLBACKS, clients_of(announcing),
           lambda metric, name: said.append(("told", metric, name)))
    return said


def who_replied(round_: MetricRound) -> tuple[str, ...]:
    """Name the members whose replies a round holds, in the order it holds them."""
    return tuple(reply.member.name for reply in round_.replies)


def test_members_are_asked_in_roster_order():
    # Ordered by cost, which is what makes an escalation policy mean anything.
    roster = Roster((member("cheap"), member("dear"), member("dearest")))
    run = assess(RAW_ADVISORY, roster, FALLBACKS, clients_of(replying()))
    assert run.asked == ("cheap", "dear", "dearest")
    assert who_replied(run.rounds[0]) == ("cheap", "dear", "dearest")


def test_one_member_answers_every_metric_before_the_next_member_is_asked():
    # Two local members that do not fit in memory together are swapped whenever
    # the member changes, so it changes once per advisory rather than every call.
    asked = [(name, metric) for kind, metric, name in calls_made() if kind == "asked"]
    assert asked == list(product(PAIR, METRIC_ORDER))


def test_the_run_reads_metric_by_metric_whatever_order_the_calls_came_in():
    roster = Roster(tuple(member(name) for name in PAIR))
    run = assess(RAW_ADVISORY, roster, FALLBACKS, clients_of(replying()))
    assert tuple(round_.metric for round_ in run.rounds) == METRIC_ORDER
    assert [who_replied(round_) for round_ in run.rounds] == [PAIR] * len(METRIC_ORDER)


def test_every_member_asked_is_announced_before_it_is_asked():
    # Otherwise a 288-call run is silent from its first call to its last (measured:
    # `measurements/council_runs/`), and the announcement has to come first: a
    # slow member is a line that sits there, not one that arrives once the wait
    # is over.
    said = calls_made()
    assert len(said) == 32
    assert said[0] == ("told", "AV", "one")
    assert said[1] == ("asked", "AV", "one")
