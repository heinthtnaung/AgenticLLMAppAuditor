"""Guards on the chat prompt: eight metrics, the council's definitions, the rules, its version."""

import json
import re
from collections import Counter
from hashlib import sha256

import pytest

import eval_samples as samples
from council.definitions import definition_of
from council.prompt import PROMPT_VERSION, REVERSED_PROMPT_VERSION, build_prompt, describe
from council.reply_format import NO_EVIDENCE_VALUE, REQUIRED_FIELDS
from cvss.metrics import METRIC_ORDER
from council_eval.chat_prompt import (
    CHAT_PROMPT_VERSION,
    PROMPT_ID_FIELD,
    chat_prompt_body,
    chat_prompt_file,
    definition_texts,
    prompt_id,
)
from council_eval.variants import CHAT, CHAT_REVERSED

# The chat prompt's words, fingerprinted as `tests/council/test_prompt.py` does the
# council's: wording that moves without its version moving fails here.
CHAT_FINGERPRINTS = {
    "chat-all-base-metrics-1": "0002500c40b67a7b85237a6cea3f659221ff3c1de91b59413bc05ee777f3b387",
    "chat-all-base-metrics-1+reversed-1":
        "c0c9fe3c1bfa4aab1970288003ef4fa75f377af46bbadba97c6f8783c3e38beb",
}
# The words that would tell a chat which order it reads, in any case.
ORDER_WORDS = ("forward", "reversed", "order")
RULES = (
    "1. Use only the text under ADVISORY below.",
    "2. Do not browse the web, and do not use anything you remember",
    "3. Support each value with a quotation copied word for word from the advisory.",
    f"4. If the advisory says nothing that supports any value of a metric, answer\n"
    f"   {NO_EVIDENCE_VALUE} for that metric.",
    "5. Reply with exactly one fenced JSON block",
)


def body(reversed_options: bool = False) -> str:
    """Render the sample advisory's prompt body in one order."""
    return chat_prompt_body(samples.ADVISORY_TEXT, reversed_options)


def words(text: str) -> Counter:
    """Count a text's words, whatever order they stand in."""
    return Counter(re.findall(r"\w+", text))


def reply_shape(text: str) -> dict:
    """Decode the reply format's fenced block, which is valid JSON by construction."""
    return json.loads(re.search(r"```json\n(.*?)\n```", text, flags=re.DOTALL).group(1))


def value_order(text: str, metric: str) -> list[str]:
    """Read the order of one metric's 'X = meaning' lines."""
    section = text.split(describe(metric), 1)[1].split("\n\n", 1)[0]
    return re.findall(r"^(\w+) = ", section, flags=re.MULTILINE)


@pytest.mark.parametrize("variant", (CHAT, CHAT_REVERSED), ids=("forward", "reversed"))
def test_the_wording_has_not_moved_without_the_version_moving(variant):
    rendered = body(variant.reversed_options)
    assert sha256(rendered.encode("utf-8")).hexdigest() == CHAT_FINGERPRINTS[variant.prompt_version]


def test_the_batched_prompt_is_a_version_of_its_own_and_not_the_council_s():
    # A known gap, asserted so that closing it turns this red: a pasted reply
    # answers eight metrics in one message, a different question from the
    # council's one metric per call, and no figure may compare the two as one.
    assert CHAT_PROMPT_VERSION not in (PROMPT_VERSION, REVERSED_PROMPT_VERSION)
    assert not CHAT.prompt_version.startswith(PROMPT_VERSION)


def test_the_definitions_and_the_advisory_share_one_message():
    # A known gap, asserted so that closing it turns this red. The council keeps
    # them in two turns because one turn made a local model quote the
    # definitions back; a chat is one message, so `chat-replies` counts that.
    rendered = body()
    assert samples.ADVISORY_TEXT.strip() in rendered
    assert all(text in rendered for text in definition_texts())
    council = build_prompt("AV", samples.ADVISORY_TEXT)
    assert samples.ADVISORY_TEXT.strip() not in council.system
    assert definition_of("AV").measures not in council.user


@pytest.mark.parametrize("metric", METRIC_ORDER)
def test_every_metric_is_asked_with_the_council_s_definition(metric):
    rendered = body()
    assert describe(metric) in rendered
    assert all(meaning in rendered for meaning in definition_of(metric).value_meanings.values())


def test_the_rules_are_a_short_numbered_list():
    rendered = body()
    assert all(rule in rendered for rule in RULES)
    assert not re.search(r"^6\. ", rendered, flags=re.MULTILINE)


@pytest.mark.parametrize("reversed_options", (False, True), ids=("forward", "reversed"))
def test_the_reply_format_is_one_object_keyed_by_metric_with_the_council_s_fields(reversed_options):
    shape = reply_shape(body(reversed_options))
    assert list(shape) == [PROMPT_ID_FIELD, *METRIC_ORDER]
    assert all(tuple(shape[metric]) == REQUIRED_FIELDS for metric in METRIC_ORDER)


@pytest.mark.parametrize("metric", METRIC_ORDER)
def test_the_reversed_prompt_lists_every_option_the_other_way_round_in_both_places(metric):
    forward = list(definition_of(metric).value_meanings)
    assert value_order(body(), metric) == forward
    assert value_order(body(True), metric) == forward[::-1]
    listed = reply_shape(body(True))[metric]["value"]
    assert listed == f"one of {', '.join(forward[::-1])} -- or {NO_EVIDENCE_VALUE}"


def test_the_id_alone_closes_the_file_and_is_the_body_s_digest():
    rendered = body(True)
    pasted = chat_prompt_file(rendered)
    assert pasted == f"{rendered}\nPROMPT-ID: {prompt_id(rendered)}\n"
    assert sha256(rendered.encode("utf-8")).hexdigest().startswith(prompt_id(rendered))
    assert prompt_id(rendered) not in rendered


@pytest.mark.parametrize("reversed_options", (False, True), ids=("forward", "reversed"))
def test_nothing_pasted_names_the_order_its_options_are_in(reversed_options):
    # A chat told it reads the reversed list could answer the telling, not the list.
    pasted = chat_prompt_file(body(reversed_options)).lower()
    assert [word for word in ORDER_WORDS if word in pasted] == []


def test_the_two_orders_hold_the_same_words_in_another_order_and_another_id():
    pasted = (chat_prompt_file(body(reversed_options)) for reversed_options in (False, True))
    forward, reversed_ = (text.splitlines()[:-1] for text in pasted)
    assert forward != reversed_
    assert words("\n".join(forward)) == words("\n".join(reversed_))


def test_the_two_orders_are_two_prompts_with_two_ids():
    assert prompt_id(body()) != prompt_id(body(True))
