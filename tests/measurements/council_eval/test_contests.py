"""Guards on the cross-check measures: lone settlements, and contests that caught an error."""

import eval_samples as samples
from council.ruling import Basis
from council_eval.contests import contest_measures
from cvss.metrics import METRIC_ORDER
from report.council_record import (
    CouncilWithoutVector,
    MemberIdentity,
    MemberSaid,
    MetricRuling,
    Outcome,
    SaidKind,
)

WHO = MemberIdentity("m", "ollama", "m", "m", ran_local=True, prompt_version="v")
AGREEING = {"redhat": samples.VECTORS["redhat"], "ghsa": samples.VECTORS["ghsa"]}


def quoted(value: str, verified: bool = True) -> MemberSaid:
    """Build a member's answer with a quotation, found in the advisory or not."""
    return MemberSaid(WHO, SaidKind.ANSWERED, value, "text", "high", verified=verified)


def record(key: str, av: MetricRuling) -> CouncilWithoutVector:
    """Build an item's record: the given Attack Vector ruling, every other metric unresolved."""
    rest = tuple(MetricRuling(metric, Outcome.UNRESOLVED, ()) for metric in METRIC_ORDER[1:])
    return CouncilWithoutVector(advisory_id=key, single_assessor=False, rulings=(av, *rest))


def attack_vector(*outcomes):
    """Measure Attack Vector's cross-check over items whose sources agree it is N."""
    items = tuple(samples.item(one.advisory_id, AGREEING) for one in outcomes)
    return contest_measures(items, outcomes)[0]


def test_a_value_settled_on_one_quotation_alone_is_counted():
    sole = MetricRuling("AV", Outcome.SETTLED, (quoted("N"),), value="N", basis=Basis.SOLE.value)
    both = (quoted("N"), quoted("N"))
    agreed = MetricRuling("AV", Outcome.SETTLED, both, value="N", basis=Basis.AGREED.value)
    measure = attack_vector(record("CVE-1", sole), record("CVE-2", agreed))
    assert (measure.settled, measure.sole) == (2, 1)


def test_a_contest_with_r1_s_value_among_the_verified_caught_an_error():
    contest = MetricRuling("AV", Outcome.CONTESTED, (quoted("N"), quoted("L")))
    measure = attack_vector(record("CVE-1", contest))
    assert (measure.contested, measure.contested_referenced, measure.caught) == (1, 1, 1)


def test_a_contest_between_two_wrong_readings_caught_nothing():
    contest = MetricRuling("AV", Outcome.CONTESTED, (quoted("A"), quoted("L")))
    assert attack_vector(record("CVE-1", contest)).caught == 0


def test_r1_s_value_quoted_without_verifying_does_not_count_as_caught():
    contest = MetricRuling("AV", Outcome.CONTESTED, (quoted("A"), quoted("L"), quoted("N", False)))
    assert attack_vector(record("CVE-1", contest)).caught == 0
