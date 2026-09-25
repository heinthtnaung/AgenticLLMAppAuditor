"""Guards on finding the object in a reply: prose around it read, a second object refused."""

import pytest

import model_shapes as shapes
from council.reply_object import MalformedReply, excerpt, extract_object, objects_in


def test_an_object_wrapped_in_prose_is_found():
    assert extract_object('Here it is: {"value": "N"} and that is all.') == {"value": "N"}


def test_an_answer_a_thinking_model_fenced_in_markdown_is_found():
    # Recorded from gemma4:latest, asked with `think` true and no `format`.
    assert extract_object(shapes.THINKING_WITHOUT_FORMAT["response"])["value"] == "N"


def test_an_object_inside_another_is_part_of_it_and_not_a_second():
    assert objects_in('{"value": "N", "note": {"a": 1}}') == [{"value": "N", "note": {"a": 1}}]


def test_braces_around_something_that_is_not_json_are_passed_over():
    assert objects_in('a {set} of words, then {"value": "N"}') == [{"value": "N"}]


def test_two_objects_are_refused_rather_than_either_being_read():
    with pytest.raises(MalformedReply, match="holds 2 JSON objects"):
        extract_object(f"{shapes.DRAFT} {shapes.ANSWER}")


def test_a_draft_in_reasoning_the_server_left_inline_is_refused():
    with pytest.raises(MalformedReply, match="holds 2 JSON objects"):
        extract_object(shapes.INLINE_DRAFT)


def test_a_reply_with_no_whole_object_is_refused_quoting_it():
    said = "No complete JSON object in the reply -- the reply began"
    with pytest.raises(MalformedReply, match=said):
        extract_object('{"value": "N", "evid')


def test_an_empty_reply_is_refused():
    with pytest.raises(MalformedReply, match="nothing at all"):
        extract_object("   ")


def test_an_excerpt_folds_the_reply_s_whitespace_and_stops_at_its_length():
    assert excerpt("a\n   b") == "the reply began 'a b'"
    assert excerpt("x" * 1000) == f"the reply began '{'x' * 300}'"
