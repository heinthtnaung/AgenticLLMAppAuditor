"""Guards on reconciliation: evidence decides, nothing is counted, and no score appears."""

import pytest

from council.answer import Confidence
from council.chairman import agreed_vector, rule_on_metric
from council.ruling import (
    Basis, ContestedMetric, NoFallbackPublished, PublishedFallback, SettledMetric,
    UnresolvedMetric,
)
from council_samples import (
    ACROSS_A_LINE_BREAK, ADVISORY, NETWORK_QUOTATION, NOT_IN_THE_ADVISORY, answer,
    found_nothing, guessed,
)

FALLBACK = PublishedFallback(value="L", source="nvd")
NOTHING_PUBLISHED = NoFallbackPublished(reason="no source published a v3 vector")


def rule(replies, metric="AV", fallback=FALLBACK):
    """Rule on one metric from the replies a test is about."""
    return rule_on_metric(metric, replies, ADVISORY, fallback)


def test_members_that_agree_settle_the_metric():
    ruling = rule([answer(name="one"), answer(name="two"), answer(name="three")])
    assert isinstance(ruling, SettledMetric)
    assert ruling.value == "N"
    assert ruling.basis is Basis.AGREED
    assert len(ruling.supporting) == 3


def test_agreement_takes_the_confidence_of_its_weakest_member():
    ruling = rule([
        answer(name="one", confidence=Confidence.HIGH),
        answer(name="two", confidence=Confidence.LOW),
    ])
    assert ruling.confidence is Confidence.LOW


def test_one_verified_quotation_beats_three_unverified_ones():
    # The anti-majority case. Three members say AV:L and one says AV:N, and the
    # one is the only quotation in the advisory. Counting would give AV:L.
    replies = [
        answer(name="one", value="L", evidence=NOT_IN_THE_ADVISORY),
        answer(name="two", value="L", evidence=NOT_IN_THE_ADVISORY),
        answer(name="three", value="L", evidence=NOT_IN_THE_ADVISORY),
        answer(name="four", value="N", evidence=NETWORK_QUOTATION),
    ]
    ruling = rule(replies)
    assert isinstance(ruling, SettledMetric)
    assert ruling.value == "N"
    assert ruling.basis is Basis.EVIDENCE
    assert [supporting.member.name for supporting in ruling.supporting] == ["four"]


def test_a_dissenter_without_a_quotation_does_not_contest_the_metric():
    replies = [
        answer(name="one", value="N", evidence=NETWORK_QUOTATION),
        answer(name="two", value="N", evidence=ACROSS_A_LINE_BREAK),
        answer(name="three", value="L", evidence=NOT_IN_THE_ADVISORY),
    ]
    ruling = rule(replies)
    assert isinstance(ruling, SettledMetric)
    assert ruling.basis is Basis.EVIDENCE


def test_two_verified_quotations_pulling_apart_are_contested():
    replies = [
        answer(name="one", value="N", evidence=NETWORK_QUOTATION),
        answer(name="two", value="L", evidence=ACROSS_A_LINE_BREAK),
    ]
    ruling = rule(replies)
    assert isinstance(ruling, ContestedMetric)
    assert {candidate.value for candidate in ruling.candidates} == {"N", "L"}
    assert not hasattr(ruling, "value")


def test_no_member_finding_evidence_is_unresolved_and_falls_back():
    ruling = rule([found_nothing(name="one"), found_nothing(name="two")])
    assert isinstance(ruling, UnresolvedMetric)
    assert ruling.fallback.value == "L"
    assert ruling.fallback.source == "nvd"


def test_answers_nobody_could_verify_are_unresolved_rather_than_agreed():
    # Three members agreeing on a quotation that is not in the advisory have
    # agreed about nothing this council can stand behind.
    replies = [answer(name=str(n), evidence=NOT_IN_THE_ADVISORY) for n in range(3)]
    ruling = rule(replies)
    assert isinstance(ruling, UnresolvedMetric)


def test_an_unresolved_metric_records_that_nothing_was_published_either():
    ruling = rule([found_nothing()], fallback=NOTHING_PUBLISHED)
    assert isinstance(ruling, UnresolvedMetric)
    assert ruling.fallback.reason.startswith("no source")


def test_a_single_assessor_can_settle_or_go_unresolved_but_never_contested():
    # `docs/COUNCIL.md`: with no cross-check, contested cannot arise at n = 1.
    settled = rule([answer(evidence=NETWORK_QUOTATION)])
    unresolved = rule([answer(evidence=NOT_IN_THE_ADVISORY)])
    assert isinstance(settled, SettledMetric)
    assert isinstance(unresolved, UnresolvedMetric)


def test_replies_about_another_metric_are_refused():
    with pytest.raises(ValueError, match="S answered where AV was asked"):
        rule([answer(metric="AV"), answer(metric="S", value="C", name="two")])


def test_the_same_replies_always_give_the_same_ruling():
    replies = [answer(name="one"), answer(name="two", confidence=Confidence.MEDIUM)]
    assert rule(replies) == rule(replies)


def settled_everywhere():
    """Rule every metric settled, so a test can change one and see the effect."""
    values = {"AV": "N", "AC": "L", "PR": "N", "UI": "N", "S": "U", "C": "H", "I": "H", "A": "H"}
    return {
        metric: rule_on_metric(
            metric, [answer(metric=metric, value=value)], ADVISORY, FALLBACK
        )
        for metric, value in values.items()
    }


def test_the_chairman_hands_over_a_vector():
    vector = agreed_vector(settled_everywhere(), version="3.1")
    assert str(vector) == "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"


def test_an_unresolved_metric_puts_its_published_fallback_in_the_vector():
    rulings = settled_everywhere()
    rulings["AV"] = rule_on_metric("AV", [found_nothing()], ADVISORY, FALLBACK)
    assert str(agreed_vector(rulings, version="3.1")).startswith("CVSS:3.1/AV:L/")


def test_a_vector_is_refused_while_a_metric_is_contested():
    rulings = settled_everywhere()
    rulings["S"] = ContestedMetric(
        "S", (answer(metric="S", value="U"), answer(metric="S", value="C"))
    )
    with pytest.raises(ValueError, match="No value for S;"):
        agreed_vector(rulings, version="3.1")


def test_a_vector_is_refused_when_an_unresolved_metric_has_no_fallback():
    rulings = settled_everywhere()
    rulings["S"] = rule_on_metric("S", [found_nothing("S")], ADVISORY, NOTHING_PUBLISHED)
    with pytest.raises(ValueError, match="No value for S;"):
        agreed_vector(rulings, version="3.1")


def test_every_unfinished_metric_is_named_at_once():
    # One round of escalation, not one metric at a time.
    rulings = settled_everywhere()
    rulings["S"] = ContestedMetric(
        "S", (answer(metric="S", value="U"), answer(metric="S", value="C"))
    )
    rulings["UI"] = rule_on_metric("UI", [found_nothing("UI")], ADVISORY, NOTHING_PUBLISHED)
    with pytest.raises(ValueError, match="No value for S, UI;"):
        agreed_vector(rulings, version="3.1")


def test_a_vector_is_refused_while_a_metric_has_no_ruling_at_all():
    rulings = settled_everywhere()
    del rulings["UI"]
    with pytest.raises(ValueError, match="No ruling on UI"):
        agreed_vector(rulings, version="3.1")



def test_a_guess_cannot_settle_a_metric():
    # Unverified is unverified. A model sounding confident does not bend
    # "evidence decides", and three guesses agreeing are still no evidence.
    ruling = rule([guessed(name="one"), guessed(name="two"), guessed(name="three")])
    assert isinstance(ruling, UnresolvedMetric)


def test_a_guess_cannot_make_a_metric_contested():
    ruling = rule([answer(value="N"), guessed(value="L", name="two")])
    assert isinstance(ruling, SettledMetric)
    assert ruling.value == "N"


def test_a_guess_is_not_recorded_as_supporting_the_ruling():
    ruling = rule([answer(name="one"), guessed(value="L", name="two")])
    assert [item.member.name for item in ruling.supporting] == ["one"]
