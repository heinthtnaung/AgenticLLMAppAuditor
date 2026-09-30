"""Guards on the order check: one reply from two readings, a value kept only where both give it."""

from dataclasses import replace

import pytest

from council.answer import (
    Confidence,
    MemberAnswer,
    MemberFoundNoEvidence,
    MemberGuessed,
    MemberOrderSensitive,
)
from council.evidence import is_quotation_from
from council.order_check import reconciled
from council.prompt import PROMPT_VERSION, REVERSED_PROMPT_VERSION, value_lines
from council.run import MemberFailure
from council_samples import ADVISORY, NOT_IN_THE_ADVISORY, QUOTABLE, identity

# The member as each call names it, and as the reconciled reply names it.
IN_ORDER = identity(prompt_version=PROMPT_VERSION)
REVERSED = identity(prompt_version=REVERSED_PROMPT_VERSION)
BOTH = identity(prompt_version=PROMPT_VERSION, reversed_prompt_version=REVERSED_PROMPT_VERSION)

# The metrics with three options, whose middle one reversing cannot move.
MIDDLE_OPTION_METRICS = ("PR", "C", "I", "A")
OPTIONS_WITH_A_MIDDLE = 3
MIDDLE_OPTION = "L"


def answer(value: str, member=IN_ORDER, metric: str = "AV") -> MemberAnswer:
    """Give a quoted answer to one metric, AV unless another is named."""
    return MemberAnswer(
        metric=metric, value=value, evidence=QUOTABLE, confidence=Confidence.HIGH, member=member
    )


def guess(value: str, member=IN_ORDER) -> MemberGuessed:
    """Give an unquoted answer to AV."""
    return MemberGuessed(metric="AV", value=value, member=member)


def decline(member=IN_ORDER) -> MemberFoundNoEvidence:
    """Give a decline on AV."""
    return MemberFoundNoEvidence(metric="AV", member=member)


def failure(member=IN_ORDER, reason: str = "timed out") -> MemberFailure:
    """Give a failed call on AV."""
    return MemberFailure(member=member, metric="AV", reason=reason)


def test_the_same_value_both_ways_keeps_the_in_order_reply_quotation_and_all():
    assert reconciled(answer("N"), answer("N", REVERSED)) == answer("N", BOTH)
    assert reconciled(guess("N"), answer("N", REVERSED)) == guess("N", BOTH)


def test_a_quotation_found_only_reversed_leaves_the_in_order_reply_unverified_on_purpose():
    """A gap kept on purpose: the in-order reply stands unverified though the reversed one holds."""
    # RED HERE MEANS THE RULE HAS CHANGED, not that something broke. Keeping the
    # reversed reply instead was replayed through the product's order check from
    # the saved passes in `measurements/council_eval_runs/`: it settled 5 more of
    # Qwen + Llama's 144 metrics, and the 3 of those with an R1 value all
    # disagreed with it -- 6 of 17 agreed across the seven rosters replayed --
    # because a quotation found in the advisory need not bear on the value.
    unverified = MemberAnswer("AV", "N", NOT_IN_THE_ADVISORY, Confidence.HIGH, IN_ORDER)
    both_ways = reconciled(unverified, answer("N", REVERSED))
    assert both_ways == replace(unverified, member=BOTH)
    assert not is_quotation_from(both_ways.evidence, ADVISORY)
    assert is_quotation_from(QUOTABLE, ADVISORY)


def test_two_different_values_are_kept_both_as_an_order_sensitive_reply():
    expected = MemberOrderSensitive(metric="AV", in_order_value="N", reversed_value="L", member=BOTH)
    assert reconciled(answer("N"), guess("L", REVERSED)) == expected


@pytest.mark.parametrize(
    "in_order, reversed_order",
    [(decline(), answer("N", REVERSED)), (answer("N"), decline(REVERSED))],
)
def test_a_decline_in_either_order_is_a_decline(in_order, reversed_order):
    assert reconciled(in_order, reversed_order) == decline(BOTH)


def test_a_failure_in_either_order_is_the_member_failing_and_says_which():
    assert reconciled(failure(), answer("N", REVERSED)) == failure(BOTH)
    failed = reconciled(answer("N"), failure(REVERSED))
    assert (failed.reason, failed.member) == ("with the options reversed: timed out", BOTH)


def test_a_decline_in_order_and_a_failure_reversed_is_the_failure_not_the_decline():
    reversed_failure = failure(BOTH, "with the options reversed: timed out")
    assert reconciled(decline(), failure(REVERSED)) == reversed_failure


def test_a_failure_both_ways_is_the_in_order_failure():
    assert reconciled(failure(), failure(REVERSED, "refused")) == failure(BOTH)


def test_every_reconciled_reply_names_both_prompts_the_member_saw():
    readings = [answer("N"), guess("L"), decline(), failure()]
    replies = [reconciled(one, answer("N", REVERSED)) for one in readings]
    assert {reply.member for reply in replies} == {BOTH}
    assert BOTH.reversed_prompt_version == REVERSED_PROMPT_VERSION


def test_readings_of_two_members_or_two_metrics_are_refused():
    other = identity("other-local", prompt_version=REVERSED_PROMPT_VERSION)
    with pytest.raises(ValueError, match="small-local on AV cannot be reconciled with other-local"):
        reconciled(answer("N"), answer("N", other))
    with pytest.raises(ValueError, match="with small-local on AC"):
        reconciled(answer("N"), MemberGuessed(metric="AC", value="L", member=REVERSED))


@pytest.mark.parametrize("metric", MIDDLE_OPTION_METRICS)
def test_a_lean_to_the_middle_option_passes_the_check_which_is_the_known_gap(metric):
    """The gap `order_check` documents, asserted so that closing it cannot happen unremarked."""
    # RED HERE MEANS THE GAP HAS BEEN CLOSED, not that something broke. Reversing
    # a list of three leaves its middle option in the middle, so a member that
    # always names the middle one names it both ways and counts as stable. If a
    # check now catches that, correct `order_check`'s docstring in the same commit
    # and rewrite this as the test of the new behaviour.
    in_order, reversed_order = value_lines(metric), value_lines(metric, reversed_options=True)
    assert len(in_order) == OPTIONS_WITH_A_MIDDLE
    assert in_order[1] == reversed_order[1]
    assert in_order[1].startswith(f"{MIDDLE_OPTION} = ")
    both_ways = reconciled(
        answer(MIDDLE_OPTION, metric=metric), answer(MIDDLE_OPTION, REVERSED, metric)
    )
    assert both_ways == answer(MIDDLE_OPTION, BOTH, metric)
