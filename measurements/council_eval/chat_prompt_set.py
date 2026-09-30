"""Every prompt of a dataset to paste into a chat: one per advisory and order of the options.

**A file is named by its PROMPT-ID, never by the advisory's id or the order.** A
chat shown an attached file shows the model its name as well: a name carrying the
CVE id would hand over what the redaction took out of the text, and one saying
`reversed` what the reversal is there to test. Only the manifest, which is never
pasted, ties a name to an advisory and an order.
"""

from dataclasses import dataclass
from itertools import product

from cli.council_run import advisory_text
from council.redaction import redact
from council_eval.chat_prompt import (
    REVERSED,
    chat_prompt_body,
    chat_prompt_file,
    order_name,
    prompt_id,
    text_digest,
)
from council_eval.dataset import Item

FILE_PREFIX = "chat-prompt"
PROMPT_SUFFIX = ".txt"
ORDERS_ASKED = (False, True)


@dataclass(frozen=True)
class ChatPrompt:
    """One prompt to paste: the item and order it asks, its file's name, and its words."""

    key: str
    order: str
    body: str
    advisory_shown: str

    @property
    def reversed_options(self) -> bool:
        """Say whether this prompt lists each metric's options reversed."""
        return self.order == REVERSED

    @property
    def prompt_id(self) -> str:
        """Give the ID a reply repeats to say which prompt it answers."""
        return prompt_id(self.body)

    @property
    def file(self) -> str:
        """Name the file a person pastes this from, by the prompt's ID alone."""
        return f"{FILE_PREFIX}-{self.prompt_id}{PROMPT_SUFFIX}"

    @property
    def sha256(self) -> str:
        """Fingerprint the prompt's body, whose first characters are its ID."""
        return text_digest(self.body)

    @property
    def text(self) -> str:
        """Give the whole file a person pastes: the body, then its ID."""
        return chat_prompt_file(self.body)


def chat_prompts(items: tuple[Item, ...]) -> tuple[ChatPrompt, ...]:
    """Build every item's prompt, forward then reversed, in the dataset's order."""
    built = tuple(chat_prompt(item, order) for item, order in product(items, ORDERS_ASKED))
    refuse_shared_ids(built)
    return built


def refuse_shared_ids(prompts: tuple[ChatPrompt, ...]) -> None:
    """Refuse two advisories whose prompts are one, since no reply could say which it answers."""
    first: dict[str, ChatPrompt] = {}
    for one in prompts:
        earlier = first.setdefault(one.prompt_id, one)
        if earlier is not one:
            raise ValueError(
                f"{earlier.key} and {one.key} read alike once redacted, so both are asked by "
                f"{one.file}, and a reply could not say which advisory it answers"
            )


def chat_prompt(item: Item, reversed_options: bool) -> ChatPrompt:
    """Build one item's prompt in one order of the options."""
    shown = shown_advisory(item)
    return ChatPrompt(
        key=item.key,
        order=order_name(reversed_options),
        body=chat_prompt_body(shown, reversed_options),
        advisory_shown=shown,
    )


def shown_advisory(item: Item) -> str:
    """Give the advisory as a council member reads it: the product's description, redacted."""
    return redact(advisory_text(item.finding)).text
