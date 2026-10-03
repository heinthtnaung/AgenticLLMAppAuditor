"""Guards on matching pasted replies to their prompts: every prompt once, both orders, one model."""

import pytest

import chat_samples
from council_eval.chat_passes import answered_prompts
from council_eval.chat_reply import ChatReply
from council_eval.chat_reply_file import RefusedReply, SavedReply

TWO_ITEMS = chat_samples.TWO_ITEMS
PROMPTS = chat_samples.prompts(TWO_ITEMS)


def reply(prompt_id: str, file: str, model: str = "m", interface: str = "web") -> ChatReply:
    """Build a read reply naming one prompt."""
    saved = SavedReply(file, model, "2026-10-01", interface, "the reply")
    return ChatReply(saved, prompt_id, chat_samples.READINGS)


def every_reply() -> list[ChatReply]:
    """Answer every prompt of the two items once, each in a file named after its prompt."""
    return [reply(one.prompt_id, f"{one.file}.reply.txt") for one in PROMPTS]


def test_every_reply_is_matched_to_its_prompt_in_the_prompts_order():
    answered = answered_prompts(PROMPTS, tuple(reversed(every_reply())))
    assert [one.prompt for one in answered] == list(PROMPTS)


def test_a_reply_naming_no_prompt_of_the_dataset_is_refused():
    stray = every_reply() + [reply("ffffffffffffffff", "stray.txt")]
    with pytest.raises(RefusedReply, match="^stray.txt: names PROMPT-ID 'ffffffffffffffff'"):
        answered_prompts(PROMPTS, tuple(stray))


def test_two_replies_to_one_prompt_are_refused():
    again = every_reply() + [reply(PROMPTS[2].prompt_id, "again.txt")]
    with pytest.raises(RefusedReply, match=f"^again.txt: answers {PROMPTS[2].file}, as"):
        answered_prompts(PROMPTS, tuple(again))


@pytest.mark.parametrize(
    "model, interface", [("other", "web"), ("m", "app")], ids=["model", "interface"]
)
def test_a_reply_from_another_model_or_interface_is_refused(model, interface):
    replies = every_reply()
    replies[3] = reply(PROMPTS[3].prompt_id, "odd.txt", model, interface)
    with pytest.raises(RefusedReply, match="^odd.txt: names .* a pass is one model's"):
        answered_prompts(PROMPTS, tuple(replies))


@pytest.mark.parametrize("missing", (1, 0), ids=["reversed twin", "forward twin"])
def test_a_reply_whose_twin_has_no_reply_is_refused(missing):
    replies = [one for index, one in enumerate(every_reply()) if index != missing]
    twin = PROMPTS[missing]
    with pytest.raises(RefusedReply, match=f"no reply answers its {twin.order} twin {twin.file}"):
        answered_prompts(PROMPTS, tuple(replies))


def test_a_prompt_nobody_answered_is_refused_by_name():
    replies = every_reply()[:2]
    missing = f"^no reply answers {PROMPTS[2].file}, {PROMPTS[3].file}"
    with pytest.raises(ValueError, match=missing):
        answered_prompts(PROMPTS, tuple(replies))


def test_no_replies_at_all_are_refused():
    with pytest.raises(ValueError, match="no replies to match"):
        answered_prompts(PROMPTS, ())
