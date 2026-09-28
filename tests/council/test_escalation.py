"""Guards on escalation's dispatch: only open metrics, both orders, one local model."""

import json

import pytest

from council.answer import MemberAnswer, MemberOrderSensitive
from council.escalation import escalate
from council.prompt import PROMPT_VERSION, REVERSED_PROMPT_VERSION
from council.roster import Roster
from council.ruling import Basis, ContestedMetric, SettledMetric
from council.run import MemberFailure
from council.runner import assess
from council.transport import ModelUnavailable
from council_samples import FALLBACKS, LEGAL_VALUE, QUOTABLE, RAW_ADVISORY, hosted, member

COUNCIL = Roster((member("one"), member("two")))
BIG = member("big-local", model="big:27b", family="big")


def answering(asked: list, by_member: dict):
    """Answer from a table of (member, metric) to value, else a legal value; note every call."""

    def said(who, prompt):
        """Answer one call, quoting the advisory so the quotation verifies."""
        asked.append((who.name, prompt.metric, prompt.version))
        value = by_member.get((who.name, prompt.metric, prompt.version), None)
        value = value or by_member.get((who.name, prompt.metric), LEGAL_VALUE[prompt.metric])
        if isinstance(value, Exception):
            raise value
        return json.dumps({"value": value, "evidence": QUOTABLE, "confidence": "high"})

    return said


# The council contests AV, one member reading it N and the other L; every other metric settles.
CONTESTING_AV = {("one", "AV"): "N", ("two", "AV"): "L"}


def escalated_run(big_says: dict) -> tuple:
    """Run the council over the sample advisory, escalate what it left open, and give every call."""
    asked = []
    clients = {"ollama": answering(asked, {**CONTESTING_AV, **big_says})}
    council = assess(RAW_ADVISORY, COUNCIL, FALLBACKS, clients, order_check=True)
    asked.clear()
    return escalate(council, RAW_ADVISORY, BIG, clients), council, asked


def test_without_an_escalation_model_the_run_is_left_exactly_as_it_was():
    asked = []
    clients = {"ollama": answering(asked, CONTESTING_AV)}
    council = assess(RAW_ADVISORY, COUNCIL, FALLBACKS, clients, order_check=True)
    before = len(asked)
    assert escalate(council, RAW_ADVISORY, None, clients) is council
    assert len(asked) == before


def test_only_the_open_metric_is_escalated_in_order_then_reversed():
    done, council, asked = escalated_run({})
    assert isinstance(council.rulings["AV"], ContestedMetric)
    assert asked == [
        ("big-local", "AV", PROMPT_VERSION), ("big-local", "AV", REVERSED_PROMPT_VERSION),
    ]
    assert [one.escalation is None for one in done.rounds] == [False, *[True] * 7]


def test_a_stable_verified_contested_value_settles_it_and_the_council_s_ruling_is_kept():
    done, council, _ = escalated_run({("big-local", "AV"): "L"})
    round_ = done.rounds[0]
    assert isinstance(round_.ruling, SettledMetric)
    assert (round_.ruling.value, round_.ruling.basis) == ("L", Basis.ESCALATED)
    assert round_.escalation.prior is council.rulings["AV"]
    assert isinstance(round_.escalation.reply, MemberAnswer)
    assert round_.escalation.reply.member.reversed_prompt_version == REVERSED_PROMPT_VERSION
    assert round_.replies == council.rounds[0].replies


def test_a_value_the_orders_disagree_on_leaves_the_metric_contested_and_is_recorded():
    flipped = {("big-local", "AV", REVERSED_PROMPT_VERSION): "L", ("big-local", "AV"): "N"}
    round_ = escalated_run(flipped)[0].rounds[0]
    assert isinstance(round_.ruling, ContestedMetric)
    assert isinstance(round_.escalation.reply, MemberOrderSensitive)


def test_a_call_that_fails_leaves_the_metric_open_and_says_which_order_failed():
    timed_out = {("big-local", "AV", REVERSED_PROMPT_VERSION): ModelUnavailable("timed out")}
    round_ = escalated_run(timed_out)[0].rounds[0]
    assert isinstance(round_.ruling, ContestedMetric)
    assert isinstance(round_.escalation.reply, MemberFailure)
    assert round_.escalation.reply.reason.startswith("with the options reversed: ")


def test_the_run_s_council_is_unchanged_by_escalating():
    done, council, _ = escalated_run({("big-local", "AV"): "L"})
    assert (done.asked, done.skipped, done.single_assessor) == (
        council.asked, council.skipped, council.single_assessor,
    )


@pytest.mark.parametrize(
    ("escalation", "said"),
    [
        (hosted("big-hosted", egress=True), "big-hosted is hosted"),
        (member("one"), "one is on the council"),
        (member("big-local", provider="elsewhere"), "no client for provider 'elsewhere'"),
    ],
    ids=["hosted", "a council member", "no client"],
)
def test_an_unfit_escalation_model_is_refused_before_it_is_asked(escalation, said):
    asked = []
    clients = {"ollama": answering(asked, CONTESTING_AV)}
    council = assess(RAW_ADVISORY, COUNCIL, FALLBACKS, clients, order_check=True)
    asked.clear()
    with pytest.raises(ValueError, match=said):
        escalate(council, RAW_ADVISORY, escalation, clients)
    assert asked == []
