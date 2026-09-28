"""Asking one model why a finding's published sources differ, and keeping only what it can quote.

**One call per finding**, carrying the disputed metrics and each source's value
on them (`council.explanation_prompt`). What comes back is kept item by item:

- **kept** -- an item on a disputed metric whose quotation is in the advisory the
  model read (`council.evidence.is_quotation_from`), the first such on its metric;
- **dropped and counted** -- an item whose quotation is not there, one about a
  metric the sources agree on, or a second on a metric already kept.

If nothing is kept the finding is not explained, and the reason is recorded, as
it is when the call fails or the reply cannot be read. **The `why` is never
checked**: it is the model's prose, and only the quotation beside it is evidence.

**Nothing here produces a number, and nothing reads an explanation back.** The
council's vector and the Organisation Risk Score are computed without it.
"""

from dataclasses import dataclass
from typing import Mapping

from council.evidence import is_quotation_from
from council.explanation_prompt import ExplanationPrompt, build_explanation_prompt
from council.explanation_reply import ExplanationItem, read_explanation
from council.providers import AskMember
from council.roster import Member
from council.transport import ModelUnavailable


@dataclass(frozen=True)
class Explained:
    """An explanation kept: the items whose quotation is in the advisory, and how many were not."""

    model: str
    prompt_version: str
    items: tuple[ExplanationItem, ...]
    dropped: int


@dataclass(frozen=True)
class NotExplained:
    """An explanation asked for and not kept, and why: failed, unreadable, or nothing kept."""

    model: str
    prompt_version: str
    because: str


Explanation = Explained | NotExplained


def explain(
    advisory_text: str, published: Mapping[str, Mapping[str, str]],
    explainer: Member, clients: Mapping[str, AskMember],
) -> Explanation:
    """Ask one model why the sources differ on the disputed metrics, and keep what it can quote."""
    prompt = build_explanation_prompt(advisory_text, published)
    try:
        items = read_explanation(clients[explainer.provider](explainer, prompt))
    # ModelUnavailable is the server; ValueError is a reply that is not the shape asked for.
    except (ModelUnavailable, ValueError) as fault:
        return NotExplained(explainer.model, prompt.version, f"no readable explanation: {fault}")
    kept = admissible(items, prompt)
    if not kept:
        return NotExplained(explainer.model, prompt.version, none_kept(len(items)))
    return Explained(explainer.model, prompt.version, kept, dropped=len(items) - len(kept))


def admissible(
    items: tuple[ExplanationItem, ...], prompt: ExplanationPrompt
) -> tuple[ExplanationItem, ...]:
    """Keep the first item on each disputed metric whose quotation is in the text the model read."""
    kept: dict[str, ExplanationItem] = {}
    for item in items:
        if item.metric in kept or not quoted_on_a_disputed_metric(item, prompt):
            continue
        kept[item.metric] = item
    return tuple(kept.values())


def quoted_on_a_disputed_metric(item: ExplanationItem, prompt: ExplanationPrompt) -> bool:
    """Say whether an item is about a disputed metric, says something, and quotes the advisory."""
    if item.metric not in prompt.metrics or not item.why:
        return False
    return is_quotation_from(item.quotation, prompt.advisory_shown)


def none_kept(offered: int) -> str:
    """Say why nothing was kept, from how many items the model offered."""
    if not offered:
        return "the model offered no item"
    items = "item" if offered == 1 else "items"
    return f"the model offered {offered} {items}, and none quoted the advisory on a disputed metric"
