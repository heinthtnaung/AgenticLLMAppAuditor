"""A reply that is not text at all still costs the ordering opinion and nothing more.

`test_planner_monotone.py` pushes every malformed *string* through the planner.
This file covers the shape that table cannot express: a reply that is not a
string. `model_client.ask` checks that a `response` key is **present** and never
checks its type, so a server answering `"response": null` -- or an object, or
bytes from something that did not decode -- reaches `_json_object` directly.

Each value below used to raise `AttributeError` or `TypeError` out of
`_json_object` and take the whole audit down. That is the falsifier for the
module's claim that "an unreadable reply is not an error here: it means no
opinion, and no opinion is a safe answer" -- a claim that has to hold for a
reply that is not text, or it is only a claim about strings.

Nothing here reaches Ollama: `ask` is injected and written in this file.
"""

import pytest

from artifacts.findings_document import MODEL_USED
from artifacts.surface import TOOL_CALL, Surface
from checks import planner
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK
from parsing.languages import PYTHON

ELIGIBLE = [PERMISSION_CHECK, SUPPLY_CHAIN_CHECK, TAINT_CHECK]

SURFACES = [Surface(TOOL_CALL, "ShellTool", "agent.py", 12, PYTHON, "tool", "langchain.tools")]

MODEL_ID = "qwen2.5-coder:7b-instruct@sha256:abc"

# The key `parse_order` reads. Named, because the dict reply below uses it: that
# reply is a well-formed answer in every respect except being text.
ORDER_KEY = "order"

# Four replies a real server can return that are not strings.
NON_TEXT_REPLIES = {
    "dict": {ORDER_KEY: [TAINT_CHECK]},
    "bytes": b'{"order": ["' + TAINT_CHECK.encode() + b'"]}',
    "none": None,
    "int": 7,
}


def answering(reply: object):
    """An `ask` that returns one fixed reply, standing in for the model.

    `object`, not `str`: the table above hands it values a real server can
    return, and a hint of `str` would quietly misdescribe them.
    """
    def ask(prompt: str) -> object:
        return reply
    return ask


@pytest.mark.parametrize("shape", sorted(NON_TEXT_REPLIES))
def test_a_reply_that_is_not_text_degrades_to_the_planned_order(shape: str) -> None:
    """No opinion, not an exception: the audit continues in the order it planned."""
    order, _ = planner.order_checks(
        SURFACES, ELIGIBLE, answering(NON_TEXT_REPLIES[shape]), MODEL_ID)
    assert order == ELIGIBLE


@pytest.mark.parametrize("shape", sorted(NON_TEXT_REPLIES))
def test_a_reply_that_is_not_text_never_removes_a_check(shape: str) -> None:
    """The one invariant holds here too: every eligible check is still in the order."""
    order, _ = planner.order_checks(
        SURFACES, ELIGIBLE, answering(NON_TEXT_REPLIES[shape]), MODEL_ID)
    assert sorted(order) == sorted(ELIGIBLE)


@pytest.mark.parametrize("shape", sorted(NON_TEXT_REPLIES))
def test_a_reply_that_is_not_text_is_still_a_model_that_answered(shape: str) -> None:
    """The server replied, so the status is `used`: unreadable is an opinion, not an outage."""
    _, record = planner.order_checks(
        SURFACES, ELIGIBLE, answering(NON_TEXT_REPLIES[shape]), MODEL_ID)
    assert record["status"] == MODEL_USED


def test_the_table_holds_every_shape_this_file_claims_to_cover() -> None:
    """Guard: an emptied table would make the three tests above pass over nothing."""
    assert len(NON_TEXT_REPLIES) == 4


def test_the_dict_reply_would_have_been_obeyed_had_it_been_text() -> None:
    """Proof the degradation above is the type check, not an unusable payload.

    Written out as a string, the same object reorders the checks. So the planned
    order asserted above is `_json_object` refusing a non-string reply, rather
    than a reply that happened to say nothing.
    """
    as_text = '{"%s": ["%s"]}' % (ORDER_KEY, TAINT_CHECK)
    order, _ = planner.order_checks(SURFACES, ELIGIBLE, answering(as_text), MODEL_ID)
    assert order == [TAINT_CHECK, PERMISSION_CHECK, SUPPLY_CHAIN_CHECK]
