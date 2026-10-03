"""Guards on what an import counts: quotations held or not, the prompt quoted back, the orders."""

import chat_samples
from council.definitions import definition_of
from council_eval.chat_passes import answered_prompts
from council_eval.chat_reply import ChatReply
from council_eval.chat_reply_file import SavedReply
from council_eval.chat_summary import order_verdicts, quotation_counts


def reply(file: str, prompt_id: str, readings: dict) -> ChatReply:
    """Build a read reply to one prompt, each metric's fields as given."""
    return ChatReply(SavedReply(file, "m", "2026-10-01", "web", ""), prompt_id, readings)


def answered_with(forward: dict, reversed_: dict):
    """Match one reply per order, each metric's fields as given."""
    ahead, behind = chat_samples.prompts()
    replies = (
        reply("f.txt", ahead.prompt_id, forward), reply("r.txt", behind.prompt_id, reversed_)
    )
    return answered_prompts(chat_samples.prompts(), replies)


def test_the_fixtures_quotations_are_counted_by_whether_the_advisory_holds_them():
    counted = quotation_counts(chat_samples.fixtures_answered())
    forward = {kind: counted[("forward", kind)] for kind in ("quoted", "verified", "unverified")}
    assert forward == {"quoted": 6, "verified": 5, "unverified": 1}
    assert (counted[("forward", "guessed")], counted[("forward", "declined")]) == (1, 1)


def test_a_quotation_of_any_metric_s_definition_is_counted_as_the_prompt_s():
    counted = quotation_counts(chat_samples.fixtures_answered())
    assert counted[("reversed", "of which a definition")] == 1
    assert counted[("forward", "of which a definition")] == 0


def test_a_definition_of_another_metric_quoted_back_is_the_prompt_s_too():
    # The chat prompt shows every metric's definitions: AV's words offered for S are the prompt.
    quoted = definition_of("AV").value_meanings["N"]
    offered = {"value": "U", "evidence": quoted, "confidence": "low"}
    borrowed = chat_samples.READINGS | {"S": offered}
    counted = quotation_counts(answered_with(borrowed, chat_samples.READINGS))
    assert counted[("forward", "of which a definition")] == 1


def test_the_two_orders_are_reconciled_as_the_audit_s_order_check_does():
    counted = order_verdicts(chat_samples.fixtures_answered())
    assert counted[("AV", "order-sensitive")] == 1
    assert counted[("C", "declined")] == 1
    assert counted[("S", "stable")] == 1
    assert sum(counted.values()) == 8


def test_a_value_guessed_the_same_both_ways_is_stable_as_the_order_check_keeps_it():
    # The fixtures guess I as N, unquoted, in both orders: `council.order_check`
    # keeps that guess, so it is stable here, and still worth nothing to the chairman.
    assert order_verdicts(chat_samples.fixtures_answered())[("I", "stable")] == 1
