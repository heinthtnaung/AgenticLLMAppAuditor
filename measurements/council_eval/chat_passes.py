"""Pasted replies matched to the prompts they name, or refused before any pass is written.

A reply names its prompt by the PROMPT-ID it repeats, and the prompts are
rebuilt here from the dataset rather than read from the files a person pasted,
so a reply to words this code would no longer write names no prompt at all.

What a pass needs, and so what is refused, each naming a file:

- **a reply to no prompt** -- another dataset's, or the words have moved since;
- **two replies to one prompt** -- which is the answer is not for this code to pick;
- **a model or an interface other than the rest's** -- a pass is one model's;
- **a reply whose twin is missing** -- an order check needs both orders;
- **a prompt nobody answered** -- a replay stops on the first call it lacks.
"""

from dataclasses import dataclass

from council_eval.chat_prompt import FORWARD, REVERSED
from council_eval.chat_prompt_set import ChatPrompt
from council_eval.chat_reply import ChatReply
from council_eval.chat_reply_file import RefusedReply

TWIN_ORDER = {FORWARD: REVERSED, REVERSED: FORWARD}


@dataclass(frozen=True)
class AnsweredPrompt:
    """One prompt, and the reply that repeated its ID."""

    prompt: ChatPrompt
    reply: ChatReply

    @property
    def file(self) -> str:
        """Name the saved reply, which is what a refusal points a person to."""
        return self.reply.saved.file


def answered_prompts(
    prompts: tuple[ChatPrompt, ...], replies: tuple[ChatReply, ...]
) -> tuple[AnsweredPrompt, ...]:
    """Match every reply to its prompt, in the prompts' order, refusing anything a pass lacks."""
    if not replies:
        raise ValueError("there are no replies to match to their prompts")
    by_id = {one.prompt_id: one for one in prompts}
    answered = tuple(AnsweredPrompt(prompt_named(by_id, one), one) for one in replies)
    refuse_repeats(answered)
    refuse_mixed_sources(answered)
    refuse_untwinned(answered, prompts)
    refuse_unanswered(answered, prompts)
    place = {one.prompt_id: index for index, one in enumerate(prompts)}
    return tuple(sorted(answered, key=lambda one: place[one.prompt.prompt_id]))


def prompt_named(by_id: dict[str, ChatPrompt], reply: ChatReply) -> ChatPrompt:
    """Give the prompt a reply names, refusing an ID no prompt of this dataset has."""
    found = by_id.get(reply.prompt_id)
    if found is None:
        raise RefusedReply(
            reply.saved.file,
            f"names PROMPT-ID {reply.prompt_id!r}, which no prompt of this dataset has: "
            "it answers another dataset's prompt, or words these prompts no longer hold",
        )
    return found


def refuse_repeats(answered: tuple[AnsweredPrompt, ...]) -> None:
    """Refuse two replies to one prompt."""
    first: dict[str, str] = {}
    for one in answered:
        earlier = first.setdefault(one.prompt.prompt_id, one.file)
        if earlier != one.file:
            raise RefusedReply(one.file, f"answers {one.prompt.file}, as {earlier} does")


def refuse_mixed_sources(answered: tuple[AnsweredPrompt, ...]) -> None:
    """Refuse replies naming more than one model, or more than one interface."""
    first = answered[0].reply.saved
    for one in answered:
        saved = one.reply.saved
        if (saved.model, saved.interface) == (first.model, first.interface):
            continue
        raise RefusedReply(
            one.file,
            f"names {saved.model!r} through {saved.interface!r}, where {first.file} names "
            f"{first.model!r} through {first.interface!r}; a pass is one model's, asked one way",
        )


def refuse_untwinned(
    answered: tuple[AnsweredPrompt, ...], prompts: tuple[ChatPrompt, ...]
) -> None:
    """Refuse a reply in one order whose twin, the same advisory in the other, has no reply."""
    twins = {(one.key, one.order): one for one in prompts}
    replied = {one.prompt.prompt_id for one in answered}
    for one in answered:
        twin = twins[(one.prompt.key, TWIN_ORDER[one.prompt.order])]
        if twin.prompt_id not in replied:
            raise RefusedReply(
                one.file,
                f"answers {one.prompt.file}, and no reply answers its {twin.order} twin "
                f"{twin.file}: an order check needs both orders",
            )


def refuse_unanswered(
    answered: tuple[AnsweredPrompt, ...], prompts: tuple[ChatPrompt, ...]
) -> None:
    """Refuse a set of replies that leaves a prompt unanswered."""
    replied = {one.prompt.prompt_id for one in answered}
    missing = [one.file for one in prompts if one.prompt_id not in replied]
    if missing:
        raise ValueError(
            f"no reply answers {', '.join(missing)}: a pass answers every prompt of its "
            "dataset, or a replay stops at the first item it has no call for"
        )
