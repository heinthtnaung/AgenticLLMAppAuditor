"""Guards on counting what members named: every reply counted, beside the option listed last."""

import eval_samples  # noqa: F401  (puts the evaluation package on the path)
from council_eval.named_values import NamedValues, counted, listed_last, named_values
from council_eval.variants import BASELINE, LIBRARY, REVERSED, Variant
from report.council_record import (
    CouncilWithoutVector,
    MemberIdentity,
    MemberSaid,
    MetricRuling,
    Outcome,
    SaidKind,
)

QWEN = MemberIdentity("qwen", "ollama", "qwen", "qwen", ran_local=True, prompt_version="v")
LLAMA = MemberIdentity("llama", "ollama", "llama", "llama", ran_local=True, prompt_version="v")


def item(key: str, *said: MemberSaid) -> CouncilWithoutVector:
    """Wrap what members said on UI into one item's record."""
    ruling = MetricRuling("UI", Outcome.UNRESOLVED, said)
    return CouncilWithoutVector(advisory_id=key, single_assessor=False, rulings=(ruling,))


def found(
    outcomes: tuple[CouncilWithoutVector, ...], variant: Variant, member: str, metric: str = "UI"
) -> NamedValues:
    """Find one member's count on one metric."""
    counts = named_values(outcomes, variant)
    return next(one for one in counts if (one.member, one.metric) == (member, metric))


OUTCOMES = (
    item("CVE-1", MemberSaid(QWEN, SaidKind.ANSWERED, "R", "q", "high", True),
         MemberSaid(LLAMA, SaidKind.GUESSED, "R")),
    item("CVE-2", MemberSaid(QWEN, SaidKind.DECLINED), MemberSaid(LLAMA, SaidKind.FAILED)),
    item("CVE-3", MemberSaid(QWEN, SaidKind.ANSWERED, "N", "q", "low", False),
         MemberSaid(LLAMA, SaidKind.ANSWERED, "R", "q", "high", True)),
)


def test_the_option_listed_last_moves_with_the_order_and_not_with_the_guidance():
    assert [listed_last("UI", one) for one in (BASELINE, LIBRARY, REVERSED)] == ["R", "R", "N"]
    assert listed_last("AV", REVERSED) == "N"


def test_every_reply_is_counted_quoted_or_guessed_and_a_decline_by_its_kind():
    assert found(OUTCOMES, BASELINE, "qwen").counts == {"R": 1, "declined": 1, "N": 1}
    assert found(OUTCOMES, BASELINE, "llama").counts == {"R": 2, "failed": 1}


def test_how_often_a_member_named_the_last_listed_is_read_against_its_own_order():
    llama = found(OUTCOMES, BASELINE, "llama")
    assert (llama.named_last, llama.items) == (2, 3)
    assert found(OUTCOMES, REVERSED, "llama").named_last == 0
    assert found(OUTCOMES, REVERSED, "qwen").named_last == 1


def test_a_metric_nobody_was_asked_counts_nothing():
    assert found(OUTCOMES, BASELINE, "qwen", "AV").counts == {}


def test_counts_are_written_commonest_first():
    assert counted({"N": 1, "R": 12, "declined": 4, "H": 1}) == "R:12 declined:4 H:1 N:1"
