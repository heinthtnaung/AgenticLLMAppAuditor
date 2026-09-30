"""Reading what the explainer said into its items, or refusing the reply loudly.

The reply is found as a member's is (`council.reply_object.extract_object`):
prose around the one JSON object is tolerated and a second object is refused,
because which one the model meant is not for this code to guess. Fields beyond
the three an item needs are passed over, as a member's are.

What is refused is a reply that is not the shape asked for -- no `items` list, an
item that is not an object, or one missing its metric, its `why` or its
quotation as text. Whether an item is kept is not decided here: that is
`council.explanation`, which holds each quotation to the advisory.

**A metric is read as its code**, in any case, **or as its name in words, spelled
exactly as `cvss.metrics` spells it**: `A`, `Availability`, `A (Availability)`
and `Availability (A)` are all `A`. gemma4 was measured writing the name, bare or
bracketed, on every call about a finding with one disputed metric. A bracketed
form whose halves are not one metric's code and name, or anything else, is kept
as written, in capitals, and so is dropped as not a disputed metric.
`council.reply` does not read a member's metric this way: a member is not asked
for one, and a metric it names other than by its code still refuses its reply.
"""

import re
from dataclasses import dataclass
from typing import Any, Mapping

from council.explanation_prompt import ITEMS_FIELD, METRIC_FIELD, QUOTATION_FIELD, WHY_FIELD
from council.reply_object import MalformedReply, excerpt, extract_object
from cvss.metrics import METRICS_BY_ABBREVIATION, METRICS_BY_NAME

ITEM_FIELDS = (METRIC_FIELD, WHY_FIELD, QUOTATION_FIELD)
# One metric written twice, the second in brackets: "AC (Attack Complexity)".
BRACKETED = re.compile(r"(?P<outer>[^()]+)\((?P<inner>[^()]+)\)")


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
        metric=read_metric(item[METRIC_FIELD]),
        why=item[WHY_FIELD].strip(),
        quotation=item[QUOTATION_FIELD],
    )


def read_metric(written: str) -> str:
    """Give the code of a metric written as its code, its name, or one beside the other."""
    stripped = written.strip()
    if stripped.upper() in METRICS_BY_ABBREVIATION:
        return stripped.upper()
    if stripped in METRICS_BY_NAME:
        return METRICS_BY_NAME[stripped].abbreviation
    return bracketed_code(stripped)


def bracketed_code(written: str) -> str:
    """Give the code of "code (name)" or "name (code)" naming one metric, else it in capitals."""
    both = BRACKETED.fullmatch(written)
    if both is None:
        return written.upper()
    outer, inner = both["outer"].strip(), both["inner"].strip()
    if is_code_and_name(outer, inner):
        return outer.upper()
    if is_code_and_name(inner, outer):
        return inner.upper()
    return written.upper()


def is_code_and_name(code: str, name: str) -> bool:
    """Say whether a code and a name in words are one Base metric's."""
    metric = METRICS_BY_NAME.get(name)
    return metric is not None and metric.abbreviation == code.upper()
