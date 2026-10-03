"""Guards on the order check: a value kept only where both orders give it, else declined."""

import pytest

import chat_samples
import eval_samples as samples
from council.prompt import PROMPT_VERSION, build_prompt
from council.providers import ollama_member
from council.reply import read_reply
from council.transport import ModelUnavailable
from council_eval import order_checked as order_checked_module
from council_eval.collect import ask_item
from council_eval.order_checked import (
    DECLINED,
    DECLINING,
    FAILED,
    ORDER_SENSITIVE,
    STABLE,
    OrderCheckedClient,
    order_checked_roster,
    verdict_of,
)
from council_eval.recording import CallRecord
from council_eval.replies import ReplayClient, ReplayMismatch, Replies
from council_eval.variants import BASELINE, LIBRARY_REVERSED, REVERSED, Variant
from report.council_record import Outcome

# Reversed, the member reads AV otherwise and declines A: AV turns order-sensitive, A declined.
REVERSED_ANSWERS = samples.ANSWERS | {"AV": samples.reply("L"), "A": samples.DECLINED}
MEMBER = ollama_member(samples.MODEL)
WHO = MEMBER.identify(PROMPT_VERSION)


def one_pass(answers: dict, variant: Variant) -> Replies:
    """Take one pass of the sample model over the sample item, asked in a variant's words."""
    records = ask_item(samples.item(), samples.MODEL, samples.FakeServer(answers), variant)
    calls = {(samples.KEY, samples.MODEL, one.metric): one for one in records}
    return Replies(headers=(samples.header(samples.MODEL, variant),), calls=calls)


def checked(forward: Replies, reversed_: Replies) -> tuple[dict, list]:
    """Rebuild the order-checked record of the sample item by metric, and its verdicts."""
    (outcome,), verdicts = order_checked_roster(
        (samples.item(),), (samples.MODEL,), forward, reversed_
    )
    return {ruling.metric: ruling for ruling in outcome.rulings}, verdicts


def read(value: str, evidence: str = samples.REMOTE):
    """Read a reply to AV as the runner reads it."""
    return read_reply(samples.reply(value, evidence=evidence), "AV", WHO)


def test_readings_that_agree_are_stable_differ_order_sensitive_and_a_decline_declines():
    assert verdict_of(read("N"), read("N", evidence="")) == STABLE
    assert verdict_of(read("N"), read("L")) == ORDER_SENSITIVE
    assert verdict_of(read("N"), read_reply(samples.DECLINED, "AV", WHO)) == DECLINED


def test_a_stable_value_keeps_the_product_order_reply_and_its_quotation():
    forward, reversed_ = one_pass(samples.ANSWERS, BASELINE), one_pass(REVERSED_ANSWERS, REVERSED)
    rulings, _ = checked(forward, reversed_)
    (said,) = rulings["UI"].said
    assert (said.value, said.evidence, said.verified) == ("N", samples.NO_INTERACTION, True)
    assert rulings["UI"].outcome is Outcome.SETTLED


def test_values_the_two_orders_do_not_share_are_recorded_as_declines():
    forward, reversed_ = one_pass(samples.ANSWERS, BASELINE), one_pass(REVERSED_ANSWERS, REVERSED)
    rulings, verdicts = checked(forward, reversed_)
    assert rulings["AV"].said[0].kind.value == "declined"
    assert rulings["A"].said[0].kind.value == "declined"
    found = {metric: verdict for _, _, metric, verdict in verdicts}
    assert (found["AV"], found["A"], found["UI"], found["C"]) == (
        ORDER_SENSITIVE, DECLINED, STABLE, DECLINED,
    )


def test_a_failure_in_either_order_is_the_member_failing():
    forward, reversed_ = one_pass(samples.ANSWERS, BASELINE), one_pass(samples.ANSWERS, REVERSED)
    key = (samples.KEY, samples.MODEL, "AV")
    reversed_.calls[key] = CallRecord("AV", reversed_.calls[key].request_sha256, None, 0.0)
    rulings, verdicts = checked(forward, reversed_)
    assert rulings["AV"].said[0].kind.value == "failed"
    assert (samples.KEY, samples.MODEL, "AV", FAILED) in verdicts


def test_the_client_answers_the_product_order_text_or_a_decline():
    forward, reversed_ = one_pass(samples.ANSWERS, BASELINE), one_pass(REVERSED_ANSWERS, REVERSED)
    client = OrderCheckedClient(
        ReplayClient(samples.KEY, forward.calls, BASELINE, samples.WINDOW),
        ReplayClient(samples.KEY, reversed_.calls, REVERSED, samples.WINDOW),
    )
    assert client(MEMBER, build_prompt("UI", samples.ADVISORY_TEXT)) == samples.ANSWERS["UI"]
    assert client(MEMBER, build_prompt("AV", samples.ADVISORY_TEXT)) == DECLINING


@pytest.mark.parametrize(
    "first, second",
    [(REVERSED, BASELINE), (BASELINE, LIBRARY_REVERSED), (BASELINE, BASELINE)],
    ids=["swapped", "library on one side only", "no reversal"],
)
def test_only_a_product_order_pass_and_its_reversal_are_paired(first, second):
    with pytest.raises(ValueError, match="pairs a pass in the product's order with one reversed"):
        checked(one_pass(samples.ANSWERS, first), one_pass(samples.ANSWERS, second))


def test_passes_at_two_windows_are_not_paired():
    reversed_ = one_pass(samples.ANSWERS, REVERSED)
    narrow = Replies(headers=(reversed_.headers[0] | {"num_ctx": 4096},), calls=reversed_.calls)
    with pytest.raises(ValueError, match="one window"):
        checked(one_pass(samples.ANSWERS, BASELINE), narrow)


@pytest.mark.parametrize("remote_side", ("forward", "reversed"))
def test_passes_one_model_took_in_two_places_are_not_paired(remote_side):
    # A member is rebuilt where its passes ran, which two places would leave unsaid.
    pair = {
        "forward": one_pass(samples.ANSWERS, BASELINE),
        "reversed": one_pass(samples.ANSWERS, REVERSED),
    }
    taken = pair[remote_side]
    pair[remote_side] = Replies(
        headers=(taken.headers[0] | {"remote_host": "192.0.2.15"},), calls=taken.calls
    )
    with pytest.raises(ValueError, match="each model took in one place"):
        checked(pair["forward"], pair["reversed"])


def test_a_reversed_pass_missing_a_call_stops_the_scoring():
    reversed_ = one_pass(samples.ANSWERS, REVERSED)
    del reversed_.calls[(samples.KEY, samples.MODEL, "S")]
    with pytest.raises(ReplayMismatch, match="no call"):
        checked(one_pass(samples.ANSWERS, BASELINE), reversed_)


def test_a_replay_fault_is_never_taken_for_a_member_failing():
    # The client passes on only what the runner records as a failure; a replay
    # fault must stop the scoring instead.
    assert not issubclass(ReplayMismatch, (ModelUnavailable, ValueError))


def test_an_order_checked_replay_names_no_escalation_model(monkeypatch):
    forward, reversed_ = one_pass(samples.ANSWERS, BASELINE), one_pass(REVERSED_ANSWERS, REVERSED)
    options = []
    monkeypatch.setattr(
        order_checked_module, "assess_one", lambda *given, **named: options.append(named)
    )
    order_checked_roster((samples.item(),), (samples.MODEL,), forward, reversed_)
    assert options == [{"order_check": False, "escalation": None}]


def test_two_pasted_passes_are_paired_with_no_window_to_compare():
    forward, reversed_ = chat_samples.fixture_passes()
    (outcome,), verdicts = order_checked_roster(
        (samples.item(),), (chat_samples.FIXTURE_MODEL,), forward, reversed_
    )
    assert (samples.KEY, chat_samples.FIXTURE_MODEL, "AV", ORDER_SENSITIVE) in verdicts
    assert (samples.KEY, chat_samples.FIXTURE_MODEL, "UI", STABLE) in verdicts


@pytest.mark.parametrize("pasted_side", ("forward", "reversed"))
def test_a_pasted_pass_is_never_paired_with_a_local_one(pasted_side):
    forward, reversed_ = chat_samples.fixture_passes()
    if pasted_side == "forward":
        pair = (forward, one_pass(REVERSED_ANSWERS, REVERSED))
    else:
        pair = (one_pass(samples.ANSWERS, BASELINE), reversed_)
    with pytest.raises(ValueError, match="pairs a pass in the product's order with one reversed"):
        checked(*pair)
