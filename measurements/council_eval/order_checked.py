"""A roster whose members count a value only where both orders of the options give it.

Qwen and Llama lean to the option the prompt lists last and Gemma to the one it
lists first, so a member's answer can be the list's order rather than a reading.
Here every member answers from two passes over the same findings, one in the
product's order and one reversed, and each finding, metric and member gets one
of four verdicts:

- **stable** -- both name the same value, and the member answers with the
  product-order reply: its quotation, its confidence, quoted or guessed;
- **order-sensitive** -- they name different values, and the member declines;
- **declined** -- either declines, and the member declines;
- **failed** -- either fails or cannot be read, and the member fails.

The chairman then works exactly as it does on any roster. The product's own
check, `council.order_check`, asks both orders in one run and records an
order-sensitive member as such rather than as a decline; it rules as this does
on every metric of the pilot's findings (`test_order_checked_product`).
"""

import json
from dataclasses import dataclass, field
from itertools import chain

from cli.council_run import assess_one
from council.answer import MemberFoundNoEvidence, MemberReply
from council.prompt import MemberPrompt
from council.reply import read_reply
from council.reply_format import CONFIDENCE_FIELD, EVIDENCE_FIELD, NO_EVIDENCE_VALUE, VALUE_FIELD
from council.roster import Member
from council.transport import ModelUnavailable
from council_eval.compose import (
    ItemClient,
    clients_for,
    item_client,
    pass_places,
    pass_roster,
    pass_variant,
    pass_window,
)
from council_eval.dataset import Item
from council_eval.replies import Replies
from council_eval.variants import PASS_ESCALATION, PASS_ORDER_CHECK
from report.council_record import CouncilOutcome

STABLE = "stable"
ORDER_SENSITIVE = "order-sensitive"
DECLINED = "declined"
FAILED = "failed"
VERDICTS = (STABLE, ORDER_SENSITIVE, DECLINED, FAILED)

# What the member is recorded as saying when its two orders do not agree.
DECLINING = json.dumps(
    {VALUE_FIELD: NO_EVIDENCE_VALUE, EVIDENCE_FIELD: "", CONFIDENCE_FIELD: "low"}
)

Verdict = tuple[str, str, str, str]


@dataclass
class OrderCheckedClient:
    """A provider client answering one item from two replays of it, and noting each verdict."""

    forward: ItemClient
    reversed: ItemClient
    verdicts: list[Verdict] = field(default_factory=list)

    def __call__(self, member: Member, prompt: MemberPrompt) -> str:
        """Answer as the product-order reply did where both orders agree, and decline otherwise."""
        who = member.identify(prompt.version)
        try:
            said = self.forward(member, prompt), self.reversed(member, prompt)
            read = [read_reply(text, prompt.metric, who) for text in said]
        except (ModelUnavailable, ValueError):
            self.note(member, prompt, FAILED)
            raise
        verdict = verdict_of(*read)
        self.note(member, prompt, verdict)
        return said[0] if verdict == STABLE else DECLINING

    def note(self, member: Member, prompt: MemberPrompt, verdict: str) -> None:
        """Keep one verdict, by item, model and metric."""
        self.verdicts.append((self.forward.key, member.model, prompt.metric, verdict))


def verdict_of(forward: MemberReply, reversed_reply: MemberReply) -> str:
    """Say whether two readings of one metric agree, differ, or were not both given."""
    if declined(forward) or declined(reversed_reply):
        return DECLINED
    return STABLE if forward.value == reversed_reply.value else ORDER_SENSITIVE


def declined(reply: MemberReply) -> bool:
    """Say whether a member declined to name a value."""
    return isinstance(reply, MemberFoundNoEvidence)


def order_checked_roster(
    items: tuple[Item, ...], models: tuple[str, ...], forward: Replies, reversed_: Replies
) -> tuple[tuple[CouncilOutcome, ...], list[Verdict]]:
    """Rebuild what an order-checked roster decides on every item, and every verdict behind it."""
    refuse_unpaired(forward, reversed_)
    orders = pass_variant(forward), pass_variant(reversed_)
    roster = pass_roster(models, orders[0], forward)
    clients = [
        OrderCheckedClient(
            item_client(item.key, forward, orders[0]),
            item_client(item.key, reversed_, orders[1]),
        )
        for item in items
    ]
    outcomes = tuple(
        assess_one(
            item.finding, roster, clients_for(roster, client),
            order_check=PASS_ORDER_CHECK, escalation=PASS_ESCALATION,
        )
        for item, client in zip(items, clients)
    )
    return outcomes, list(chain.from_iterable(client.verdicts for client in clients))


def refuse_unpaired(forward: Replies, reversed_: Replies) -> None:
    """Refuse two sets of passes that differ in anything but the order of the options."""
    ahead, behind = pass_variant(forward), pass_variant(reversed_)
    same_prompt = ahead.library == behind.library and ahead.chat == behind.chat
    if ahead.reversed_options or not behind.reversed_options or not same_prompt:
        raise ValueError(
            f"an order check pairs a pass in the product's order with one reversed, "
            f"not {ahead.prompt_version} with {behind.prompt_version}"
        )
    # A chat names no window, and nothing is rebuilt at one.
    if not ahead.chat and pass_window(forward) != pass_window(reversed_):
        raise ValueError("an order check pairs passes recorded at one window")
    # A member is rebuilt where its passes ran, so its two orders must have run in one place.
    if not ahead.chat and pass_places(forward) != pass_places(reversed_):
        raise ValueError("an order check pairs passes each model took in one place")
