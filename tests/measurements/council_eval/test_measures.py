"""Guards on the measures: per metric, three outcomes, and a baseline scored on the same items."""

import pytest

import eval_samples as samples
from cvss.metrics import METRIC_ORDER
from council_eval.measures import (
    NOT_IN_ADVISORY,
    VERIFIED,
    member_measures,
    metric_measures,
    outcome_totals,
    wilson,
)
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
# Red Hat alone on AV: R1 has nothing to say about it.
DISPUTED_AV = {
    "redhat": samples.VECTORS["redhat"],
    "ghsa": samples.VECTORS["ghsa"].replace("AV:N", "AV:L"),
}


def ruling(metric: str, outcome: Outcome, value: str = "", *said: MemberSaid) -> MetricRuling:
    """Build one metric's ruling as the report records it."""
    return MetricRuling(metric, outcome, tuple(said), value=value)


def record(key: str, *rulings: MetricRuling) -> CouncilWithoutVector:
    """Build one item's council record, every metric not given left unresolved."""
    given = {one.metric for one in rulings}
    missing = [metric for metric in METRIC_ORDER if metric not in given]
    rest = tuple(ruling(metric, Outcome.UNRESOLVED) for metric in missing)
    return CouncilWithoutVector(advisory_id=key, single_assessor=True, rulings=(*rulings, *rest))


def av_measure(outcomes, items):
    """Measure Attack Vector alone."""
    return metric_measures(items, outcomes)[0]


ITEMS = (
    samples.item("CVE-1", AGREEING),
    samples.item("CVE-2", AGREEING),
    samples.item("CVE-3", DISPUTED_AV),
)


def test_the_three_outcomes_are_counted_apart():
    outcomes = (
        record("CVE-1", ruling("AV", Outcome.SETTLED, "N")),
        record("CVE-2", ruling("AV", Outcome.CONTESTED)),
        record("CVE-3", ruling("AV", Outcome.UNRESOLVED)),
    )
    measure = av_measure(outcomes, ITEMS)
    assert (measure.settled, measure.contested, measure.unresolved) == (1, 1, 1)


def test_a_settled_value_r1_cannot_judge_is_kept_out_of_the_denominator():
    outcomes = (
        record("CVE-1", ruling("AV", Outcome.SETTLED, "N")),
        record("CVE-2", ruling("AV", Outcome.SETTLED, "L")),
        record("CVE-3", ruling("AV", Outcome.SETTLED, "L")),
    )
    measure = av_measure(outcomes, ITEMS)
    assert (measure.scored, measure.agreed, measure.unreferenced) == (2, 1, 1)
    assert measure.reference_items == 2


def test_the_baseline_answers_the_commonest_r1_value_of_the_scored_items_only():
    # CVE-2 is contested, so the baseline is not scored on it either.
    outcomes = (
        record("CVE-1", ruling("AV", Outcome.SETTLED, "L")),
        record("CVE-2", ruling("AV", Outcome.CONTESTED)),
        record("CVE-3", ruling("AV", Outcome.SETTLED, "L")),
    )
    measure = av_measure(outcomes, ITEMS)
    assert (measure.majority_value, measure.majority_hits, measure.scored) == ("N", 1, 1)


def test_the_distinct_values_settled_are_reported():
    outcomes = tuple(record(key, ruling("AV", Outcome.SETTLED, "L")) for key in ("CVE-1", "CVE-2"))
    assert av_measure(outcomes, ITEMS[:2]).values_used == ("L",)


def test_a_member_s_replies_are_counted_by_kind_telling_verified_from_not():
    said = [
        MemberSaid(WHO, SaidKind.ANSWERED, "N", "text", "high", verified=True),
        MemberSaid(WHO, SaidKind.ANSWERED, "L", "text", "high", verified=False),
        MemberSaid(WHO, SaidKind.GUESSED, "A"),
        MemberSaid(WHO, SaidKind.DECLINED),
        MemberSaid(WHO, SaidKind.FAILED, reason="timed out"),
    ]
    rulings = [ruling("AV", Outcome.UNRESOLVED, "", one) for one in said]
    outcomes = tuple(record(f"CVE-{index}", one) for index, one in enumerate(rulings))
    (attack_vector, *_) = member_measures(outcomes)
    kinds = {VERIFIED: 1, NOT_IN_ADVISORY: 1, "guessed": 1, "declined": 1, "failed": 1}
    assert attack_vector.kinds == kinds
    assert attack_vector.values_used == ("A", "L", "N")


def test_every_metric_of_every_item_is_totalled_by_outcome():
    rulings = (ruling("AV", Outcome.SETTLED, "N"), ruling("AC", Outcome.CONTESTED))
    outcomes = (record("CVE-1", *rulings),)
    assert outcome_totals(outcomes) == {"settled": 1, "contested": 1, "unresolved": 6}


def test_the_interval_is_wilson_s():
    low, high = wilson(5, 10)
    assert (round(low, 3), round(high, 3)) == (0.237, 0.763)


def test_an_empty_sample_has_no_interval():
    with pytest.raises(ValueError, match="no interval"):
        wilson(0, 0)


def test_a_record_missing_a_metric_is_refused():
    with pytest.raises(ValueError, match="holds 0 rulings on AV"):
        av_measure((CouncilWithoutVector(advisory_id="CVE-1", single_assessor=True),), ITEMS[:1])
