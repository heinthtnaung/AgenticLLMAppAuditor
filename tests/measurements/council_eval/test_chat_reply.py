"""Guards on reading a pasted reply's block: eight metrics in the council's fields, or a refusal."""

import json

import pytest

import chat_samples
from council_eval.chat_reply import read_chat_reply
from council_eval.chat_reply_file import RefusedReply, SavedReply, read_saved_reply

PROMPT_ID = "0123456789abcdef"


def saved(reply: str) -> SavedReply:
    """Wrap a reply's text as a person saved it."""
    return SavedReply("reply-07.txt", chat_samples.FIXTURE_MODEL, "2026-10-01", "web", reply)


def with_metric(metric: str, given: object) -> str:
    """Write a reply whose one metric is replaced by what a test gives."""
    return chat_samples.block(PROMPT_ID, chat_samples.READINGS | {metric: given})


def refused(reply: str, reason: str) -> None:
    """Hold that a reply is refused, naming the file and the reason."""
    with pytest.raises(RefusedReply, match=f"^reply-07.txt: .*{reason}"):
        read_chat_reply(saved(reply))


def test_the_block_is_read_from_prose_around_it_into_its_id_and_eight_metrics():
    read = read_chat_reply(saved(f"Sure.\n\n{chat_samples.block(PROMPT_ID)}\nHope that helps."))
    assert read.prompt_id == PROMPT_ID
    assert dict(read.readings) == chat_samples.READINGS


def test_the_prompt_id_is_read_whatever_its_case_or_the_space_around_it():
    block = chat_samples.block(f"  {PROMPT_ID.upper()} ")
    assert read_chat_reply(saved(block)).prompt_id == PROMPT_ID


def test_a_value_is_read_as_the_council_reads_one_the_pair_or_the_letter_in_any_case():
    pair = {"value": "av:n", "evidence": "", "confidence": "High"}
    assert read_chat_reply(saved(with_metric("AV", pair))).readings["AV"] == pair


def test_the_fixtures_read_as_replies():
    read = read_chat_reply(read_saved_reply(chat_samples.FORWARD_FIXTURE))
    assert read.readings["UI"]["evidence"] == "No user interaction is required."


def test_a_reply_with_no_fenced_block_is_refused():
    refused('{"prompt_id": "x"}', "holds no fenced JSON block")


def test_a_reply_with_two_fenced_blocks_is_refused():
    refused(chat_samples.block(PROMPT_ID) * 2, "holds 2 fenced blocks")


def test_a_block_that_is_not_json_is_refused():
    refused("```json\n{'AV': 'N'}\n```\n", "not JSON")


def test_a_block_that_is_not_an_object_is_refused():
    refused("```json\n[1, 2]\n```\n", "is a list, not an object")


def test_a_block_naming_a_metric_twice_is_refused_rather_than_read_as_its_last_word():
    twice = chat_samples.block(PROMPT_ID).replace('"AV":', '"AV": {"value": "L"}, "AV":', 1)
    refused(twice, "its block names AV more than once")


def test_a_metric_naming_a_field_twice_is_refused():
    twice = chat_samples.block(PROMPT_ID).replace('"value": "N"', '"value": "L", "value": "N"', 1)
    refused(twice, "its block names value more than once")


def test_a_block_missing_a_metric_is_refused():
    readings = {key: value for key, value in chat_samples.READINGS.items() if key != "PR"}
    refused(chat_samples.block(PROMPT_ID, readings), "has no PR")


def test_a_block_missing_the_prompt_id_is_refused():
    refused(f"```json\n{json.dumps(chat_samples.READINGS)}\n```\n", "has no prompt_id")


def test_a_block_naming_an_unknown_metric_key_is_refused():
    readings = chat_samples.READINGS | {"E": chat_samples.READINGS["AV"]}
    refused(chat_samples.block(PROMPT_ID, readings), "names E, which is no Base metric")


def test_a_prompt_id_that_is_not_text_is_refused():
    refused(chat_samples.block(1234), "prompt_id is 1234")


def test_a_metric_that_is_not_an_object_is_refused():
    refused(with_metric("S", "U"), "S is a str, not an object")


@pytest.mark.parametrize("field", ("value", "evidence", "confidence"))
def test_a_metric_missing_a_field_is_refused(field):
    given = {key: text for key, text in chat_samples.READINGS["AC"].items() if key != field}
    refused(with_metric("AC", given), f"AC has no {field}")


def test_a_metric_adding_a_field_is_refused():
    given = chat_samples.READINGS["AC"] | {"reasoning": "because"}
    refused(with_metric("AC", given), "AC adds reasoning")


@pytest.mark.parametrize("value", ("X", "P", "R", "", "NONE"), ids=("X", "P", "R", "empty", "NONE"))
def test_a_letter_the_metric_does_not_allow_is_refused(value):
    refused(with_metric("AC", chat_samples.READINGS["AC"] | {"value": value}), "AC: ")


def test_a_value_that_is_not_text_is_refused():
    refused(with_metric("AC", chat_samples.READINGS["AC"] | {"value": 1}), "AC: AC was answered")


def test_a_quotation_that_is_not_text_is_refused():
    refused(with_metric("A", chat_samples.READINGS["A"] | {"evidence": ["x"]}), "is not text")


@pytest.mark.parametrize("confidence", ("certain", "", 3))
def test_a_confidence_the_prompt_never_offered_is_refused(confidence):
    given = chat_samples.READINGS["A"] | {"confidence": confidence}
    refused(with_metric("A", given), "A's confidence .* is none of low, medium, high")
