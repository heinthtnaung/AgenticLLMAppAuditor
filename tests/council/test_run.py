"""Guards on the record of one council run: rulings by metric, and every failed call kept."""

from itertools import product

from council.roster import Roster
from council.run import MemberFailure
from council.runner import assess
from council.transport import ModelUnavailable
from cvss.metrics import METRIC_ORDER
from council_samples import FALLBACKS, RAW_ADVISORY, clients_of, member, replying


def failing(member_asked, prompt):
    """Fail every call, the way a server that is down does."""
    raise ModelUnavailable("the server said no")


def test_the_rulings_are_keyed_by_metric_in_specification_order():
    run = assess(RAW_ADVISORY, Roster((member(),)), FALLBACKS, clients_of(replying()))
    assert tuple(run.rulings) == METRIC_ORDER
    assert all(run.rulings[round_.metric] is round_.ruling for round_ in run.rounds)


def test_every_failed_call_is_kept_metric_by_metric_in_roster_order():
    roster = Roster((member("one"), member("two")))
    run = assess(RAW_ADVISORY, roster, FALLBACKS, clients_of(failing))
    assert all(isinstance(one, MemberFailure) for one in run.failures)
    kept = [(one.metric, one.member.name) for one in run.failures]
    assert kept == list(product(METRIC_ORDER, ("one", "two")))
