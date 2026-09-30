"""What an import found before any roster is scored: the quotations, and the orders held together.

**Quotations**, per order: how many a reply offered, how many the advisory it was
shown contains (`council.evidence`), and of those it does not, how many are a
definition's words. The chat prompt puts the definitions in the advisory's
message, which `council.prompt` measured as making a local model quote them
back, so this counts it rather than assumes it either way. An unverified
quotation is kept in the pass as the chat gave it; the chairman marks it so.

**Orders**, per metric: each advisory's two readings reconciled by the audit's
own order check (`council.order_check`) -- stable, order-sensitive or declined.
"""

from collections import Counter
from dataclasses import dataclass
from itertools import chain, product
from typing import Mapping

from council.answer import (
    MemberAnswer,
    MemberFoundNoEvidence,
    MemberGuessed,
    MemberOrderSensitive,
    MemberReply,
)
from council.envelope import RESPONSE_FIELD
from council.evidence import is_quotation_from
from council.order_check import reconciled
from council.reply import read_reply
from cvss.metrics import METRIC_ORDER

from council_eval.chat_pass_lines import call_of
from council_eval.chat_passes import AnsweredPrompt
from council_eval.chat_prompt import FORWARD, REVERSED
from council_eval.chat_replay import chat_member
from council_eval.order_checked import DECLINED, ORDER_SENSITIVE, STABLE
from council_eval.quoting import is_prompt_text
from council_eval.variants import CHAT, chat_variant

GUESSED = "guessed"
QUOTED = "quoted"
VERIFIED = "verified"
UNVERIFIED = "unverified"
DEFINITION = "of which a definition"
QUOTATION_KINDS = (QUOTED, VERIFIED, UNVERIFIED, DEFINITION, GUESSED, DECLINED)
ORDER_VERDICTS = (STABLE, ORDER_SENSITIVE, DECLINED)
VERDICT_OF = {
    MemberAnswer: STABLE,
    MemberGuessed: STABLE,
    MemberOrderSensitive: ORDER_SENSITIVE,
    MemberFoundNoEvidence: DECLINED,
}


@dataclass(frozen=True)
class Reading:
    """One metric of one reply, read as the product reads a member's, and the text it was shown."""

    reply: MemberReply
    advisory_shown: str


def reading(answered: AnsweredPrompt, metric: str) -> Reading:
    """Read one metric of a pasted reply exactly as the replay will."""
    said = call_of(answered, metric).envelope[RESPONSE_FIELD]
    member = chat_member(answered.reply.saved.model)
    who = member.identify(chat_variant(answered.prompt.reversed_options).prompt_version)
    return Reading(read_reply(said, metric, who), answered.prompt.advisory_shown)


def quotation_counts(answered: tuple[AnsweredPrompt, ...]) -> Counter:
    """Count every metric of every reply by what it offered, and each quotation by if it held."""
    pairs = product(answered, METRIC_ORDER)
    return Counter(chain.from_iterable(tagged(one, metric) for one, metric in pairs))


def tagged(answered: AnsweredPrompt, metric: str) -> tuple[tuple[str, str], ...]:
    """Name what one metric of one reply offered, beside the order it was asked in."""
    return tuple((answered.prompt.order, kind) for kind in kinds(reading(answered, metric), metric))


def kinds(read: Reading, metric: str) -> tuple[str, ...]:
    """Name what one metric's reading was: declined, guessed, or quoted and whether it held."""
    if isinstance(read.reply, MemberFoundNoEvidence):
        return (DECLINED,)
    if isinstance(read.reply, MemberGuessed):
        return (GUESSED,)
    if is_quotation_from(read.reply.evidence, read.advisory_shown):
        return (QUOTED, VERIFIED)
    if is_prompt_text(metric, read.reply.evidence, CHAT.added_texts):
        return (QUOTED, UNVERIFIED, DEFINITION)
    return (QUOTED, UNVERIFIED)


def order_verdicts(answered: tuple[AnsweredPrompt, ...]) -> Counter:
    """Count, per metric, how each advisory's two orders reconcile under the audit's order check."""
    twins = paired(answered)
    return Counter(
        (metric, VERDICT_OF[type(reconciled_reading(twins[key], metric))])
        for key, metric in product(twins, METRIC_ORDER)
    )


def reconciled_reading(twins: Mapping[str, AnsweredPrompt], metric: str) -> MemberReply:
    """Reconcile one advisory's two readings of one metric, as `council.order_check` does."""
    return reconciled(reading(twins[FORWARD], metric).reply, reading(twins[REVERSED], metric).reply)


def paired(answered: tuple[AnsweredPrompt, ...]) -> dict[str, dict[str, AnsweredPrompt]]:
    """Group the replies by advisory, each advisory's two by order."""
    twins: dict[str, dict[str, AnsweredPrompt]] = {}
    for one in answered:
        twins.setdefault(one.prompt.key, {})[one.prompt.order] = one
    return twins
