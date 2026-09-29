"""Guards on reading the explainer's reply: the one object found, anything not the shape refused."""

import json

import pytest

from council.explanation_reply import ExplanationItem, read_explanation
from council.reply_object import MalformedReply

ITEM = {"metric": "av", "why": "It says remote.", "quotation": "remote attacker"}


def replying(*items) -> str:
    """Give a reply of these items, as the prompt asks for it."""
    return json.dumps({"items": list(items)})


def test_prose_around_the_one_object_is_tolerated_and_the_metric_read_in_capitals():
    said = f"Here is my answer:\n```json\n{replying(ITEM)}\n```\nI hope that helps."
    assert read_explanation(said) == (ExplanationItem("AV", "It says remote.", "remote attacker"),)


def test_fields_beyond_the_three_are_passed_over_as_a_member_s_are():
    said = replying({**ITEM, "confidence": "high"})
    assert read_explanation(said)[0].metric == "AV"


def test_a_reply_holding_two_objects_is_refused_rather_than_guessed_at():
    with pytest.raises(MalformedReply, match="holds 2 JSON objects"):
        read_explanation(f"{replying(ITEM)}\n{replying(ITEM)}")


@pytest.mark.parametrize(
    ("said", "refusal"),
    [
        ("no json here", "No complete JSON object"),
        (json.dumps({"explanation": "it differs"}), "has no 'items' list"),
        (replying("AV is remote"), "An item is str, not an object"),
        (replying({"metric": "AV", "why": "remote"}), "has no quotation as text"),
        (replying({"metric": "AV", "why": 3, "quotation": "remote"}), "has no why as text"),
    ],
    ids=["no object", "no items", "an item that is text", "no quotation", "a why that is a number"],
)
def test_a_reply_not_the_shape_asked_for_is_refused_saying_what_was_wrong(said, refusal):
    with pytest.raises(MalformedReply, match=refusal):
        read_explanation(said)


def test_an_empty_list_is_read_as_no_item_rather_than_refused():
    assert read_explanation(replying()) == ()
