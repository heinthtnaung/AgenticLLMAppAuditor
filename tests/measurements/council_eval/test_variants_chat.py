"""Guards on the chat variants: the pasted prompt's own version, replayable and never collected."""

import pytest

import eval_samples as samples
from council.definitions import definition_of
from council.prompt import build_prompt
from council_eval.chat_prompt import CHAT_PROMPT_VERSION, definition_texts
from council_eval.commands import parser
from council_eval.variants import (
    ASKED_VARIANTS,
    CHAT,
    CHAT_REVERSED,
    VARIANTS,
    VariantMismatch,
    chat_variant,
    variant_asked,
    variant_prompt,
)


def test_the_chat_prompt_asks_under_its_own_version_in_each_order():
    assert CHAT.prompt_version == CHAT_PROMPT_VERSION
    assert CHAT_REVERSED.prompt_version == f"{CHAT_PROMPT_VERSION}+reversed-1"
    assert (chat_variant(False), chat_variant(True)) == (CHAT, CHAT_REVERSED)


@pytest.mark.parametrize("variant", (CHAT, CHAT_REVERSED), ids=("chat", "chat-reversed"))
def test_a_pasted_pass_is_found_by_the_version_it_was_asked_under(variant):
    assert variant_asked(variant.prompt_version) == variant
    assert variant in ASKED_VARIANTS


def test_collect_cannot_ask_a_local_model_in_the_chat_prompt():
    assert CHAT.name not in VARIANTS and CHAT_REVERSED.name not in VARIANTS
    with pytest.raises(SystemExit):
        parser().parse_args(["collect", "--dataset", "d", "--model", "m", "--out", "o",
                             "--variant", CHAT.name])


def test_a_chat_variant_is_never_made_from_the_product_s_prompt():
    with pytest.raises(VariantMismatch, match="pasted by a person, not sent"):
        variant_prompt(build_prompt("AV", samples.ADVISORY_TEXT), CHAT)


def test_every_definition_a_chat_prompt_shows_counts_as_the_prompt_s_text():
    assert CHAT.added_texts == definition_texts()
    assert definition_of("S").value_meanings["C"] in CHAT_REVERSED.added_texts
