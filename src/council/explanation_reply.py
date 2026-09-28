"""Reading what the explainer said into its items, or refusing the reply loudly.

The reply is found as a member's is (`council.reply_object.extract_object`):
prose around the one JSON object is tolerated and a second object is refused,
because which one the model meant is not for this code to guess. Fields beyond
the three an item needs are passed over, as a member's are.

What is refused is a reply that is not the shape asked for -- no `items` list, an
item that is not an object, or one missing its metric, its `why` or its
quotation as text. Whether an item is kept is not decided here: that is
`council.explanation`, which holds each quotation to the advisory.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from council.explanation_prompt import ITEMS_FIELD, METRIC_FIELD, QUOTATION_FIELD, WHY_FIELD
from council.reply_object import MalformedReply, excerpt, extract_object

ITEM_FIELDS = (METRIC_FIELD, WHY_FIELD, QUOTATION_FIELD)


@dataclass(frozen=True)
class ExplanationItem:
    """One metric the explainer spoke to: why the sources might differ, and what it quoted."""

    metric: str
    why: str
    quotation: str


def read_explanation(text: str) -> tuple[ExplanationItem, ...]:
    """Read the explainer's reply into its items, refusing one that is not the shape asked for."""
    fields = extract_object(text)
    items = fields.get(ITEMS_FIELD)
    if not isinstance(items, list):
        raise MalformedReply(f"The reply has no {ITEMS_FIELD!r} list -- {excerpt(text)}")
    return tuple(read_item(one, text) for one in items)


def read_item(item: Any, text: str) -> ExplanationItem:
    """Read one item, refusing one that is not an object of the three fields, each as text."""
    if not isinstance(item, Mapping):
        raise MalformedReply(f"An item is {type(item).__name__}, not an object -- {excerpt(text)}")
    missing = [name for name in ITEM_FIELDS if not isinstance(item.get(name), str)]
    if missing:
        raise MalformedReply(f"An item has no {', '.join(missing)} as text -- {excerpt(text)}")
    return ExplanationItem(
        metric=item[METRIC_FIELD].strip().upper(),
        why=item[WHY_FIELD].strip(),
        quotation=item[QUOTATION_FIELD],
    )
