"""How often each member named each value, beside the option its prompt listed last.

The pilot's Llama named the last-listed option of AC, UI and S on every item.
That is either a reading that happens to fall there or the list's order deciding,
and only a reversed list tells the two apart: so the count that matters is how
often a member named whatever its own prompt listed last, which moves with the
variant. Every reply is counted, quoted or guessed, because the order can decide
a value the member then fails to support; a decline or a failure is counted by
its kind, so the counts of a metric always add up to the items.
"""

from collections import Counter
from dataclasses import dataclass
from itertools import chain, product
from typing import Iterable, Mapping

from council.definitions import definition_of
from cvss.metrics import METRIC_ORDER
from report.council_record import CouncilOutcome, MemberSaid

from council_eval.variants import Variant, in_order

COUNT_SEPARATOR = ":"


@dataclass(frozen=True)
class NamedValues:
    """What one member named on one metric across the items, and the option listed last to it."""

    member: str
    metric: str
    listed_last: str
    counts: Mapping[str, int]

    @property
    def named_last(self) -> int:
        """Count the items on which the member named the option listed last."""
        return self.counts.get(self.listed_last, 0)

    @property
    def items(self) -> int:
        """Count the items the member was asked this metric on."""
        return sum(self.counts.values())


def listed_last(metric: str, variant: Variant) -> str:
    """Give the option a variant's prompt lists last for one metric."""
    return in_order(tuple(definition_of(metric).value_meanings), variant)[-1]


def named_values(
    outcomes: Iterable[CouncilOutcome], variant: Variant
) -> tuple[NamedValues, ...]:
    """Count what every member named on every metric, in the order the members first spoke."""
    rulings = chain.from_iterable(outcome.rulings for outcome in outcomes)
    spoken = list(chain.from_iterable(said_on(ruling.metric, ruling.said) for ruling in rulings))
    members = list(dict.fromkeys(said.member.name for _, said in spoken))
    pairs = product(members, METRIC_ORDER)
    return tuple(member_named(member, metric, spoken, variant) for member, metric in pairs)


def said_on(metric: str, said: tuple[MemberSaid, ...]) -> list[tuple[str, MemberSaid]]:
    """Pair every member's word on one ruling with the metric it was about."""
    return [(metric, one) for one in said]


def member_named(
    member: str, metric: str, spoken: list[tuple[str, MemberSaid]], variant: Variant
) -> NamedValues:
    """Count one member's values on one metric, a decline or a failure by its kind."""
    own = [said for asked, said in spoken if asked == metric and said.member.name == member]
    counts = Counter(said.value or said.kind.value for said in own)
    return NamedValues(member, metric, listed_last(metric, variant), dict(counts))


def counted(counts: Mapping[str, int]) -> str:
    """Give counts as 'value:count' words, commonest first, ties in name order."""
    ordered = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return " ".join(f"{value}{COUNT_SEPARATOR}{count}" for value, count in ordered)
