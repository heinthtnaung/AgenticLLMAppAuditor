"""What a roster did on each metric, measured against R1 and against answering the commonest value.

**Per metric, never one number.** Eight metrics are eight results, and they are
not equally hard: an average hides the finding.

**Three outcomes, not two.** A settled value where R1 has a reference is agreed
or disagreed; a settled value where R1 has none is neither, and is counted
beside the denominator rather than in it.

**Always against a baseline.** The baseline answers every scored item with the
commonest R1 value among those same items. It is computed on exactly the
items the council settled, because a council that settles only the easy ones
must not be compared with a constant scored on all of them.

**Check what was written.** The distinct values a roster settled on, and those
each member named, are reported beside every rate: one value throughout is a
constant, however well it scores.
"""

from collections import Counter
from dataclasses import dataclass
from itertools import chain, product
from math import sqrt
from typing import Iterable, Mapping

from cvss.metrics import METRIC_ORDER
from report.council_record import CouncilOutcome, MemberSaid, MetricRuling, Outcome, SaidKind

from council_eval.dataset import Item
from council_eval.reference import r1_reference

# A 95% interval.
Z = 1.96
NOTHING_SCORED = ""

VERIFIED = "verified"
NOT_IN_ADVISORY = "not in advisory"


@dataclass(frozen=True)
class MetricMeasure:
    """One metric across the items: its outcomes, its agreement with R1, and the baseline's."""

    metric: str
    items: int
    settled: int
    contested: int
    unresolved: int
    reference_items: int
    scored: int
    agreed: int
    majority_value: str
    majority_hits: int
    unreferenced: int
    values_used: tuple[str, ...]


@dataclass(frozen=True)
class MemberMeasure:
    """What one member did on one metric across the items, and every value it named."""

    member: str
    metric: str
    kinds: Mapping[str, int]
    values_used: tuple[str, ...]


def metric_measures(
    items: tuple[Item, ...], outcomes: tuple[CouncilOutcome, ...]
) -> tuple[MetricMeasure, ...]:
    """Measure every metric of one roster's outcomes against R1."""
    references = {item.key: r1_reference(item.finding.advisory.vectors) for item in items}
    by_key = {outcome.advisory_id: outcome for outcome in outcomes}
    return tuple(metric_measure(metric, by_key, references) for metric in METRIC_ORDER)


def metric_measure(
    metric: str,
    by_key: Mapping[str, CouncilOutcome],
    references: Mapping[str, Mapping[str, str]],
) -> MetricMeasure:
    """Measure one metric: what was settled, what R1 says of it, and what a constant would score."""
    rulings = {key: ruling_for(outcome, metric) for key, outcome in by_key.items()}
    counted = Counter(ruling.outcome for ruling in rulings.values())
    settled = {key: one.value for key, one in rulings.items() if one.outcome is Outcome.SETTLED}
    pairs = scored_pairs(metric, settled, references)
    majority_value, majority_hits = majority(reference for _, reference in pairs)
    return MetricMeasure(
        metric=metric,
        items=len(rulings),
        settled=counted[Outcome.SETTLED],
        contested=counted[Outcome.CONTESTED],
        unresolved=counted[Outcome.UNRESOLVED],
        reference_items=sum(metric in references[key] for key in rulings),
        scored=len(pairs),
        agreed=sum(value == reference for value, reference in pairs),
        majority_value=majority_value,
        majority_hits=majority_hits,
        unreferenced=len(settled) - len(pairs),
        values_used=tuple(sorted(set(settled.values()))),
    )


def scored_pairs(
    metric: str, settled: Mapping[str, str], references: Mapping[str, Mapping[str, str]]
) -> list[tuple[str, str]]:
    """Pair each settled value with R1's, for the items where R1 has a value for this metric."""
    referenced = [key for key in settled if metric in references[key]]
    return [(settled[key], references[key][metric]) for key in referenced]


def ruling_for(outcome: CouncilOutcome, metric: str) -> MetricRuling:
    """Find one metric's ruling in an item's record, refusing a record without it."""
    found = [ruling for ruling in outcome.rulings if ruling.metric == metric]
    if len(found) != 1:
        raise ValueError(f"{outcome.advisory_id} holds {len(found)} rulings on {metric}")
    return found[0]


def majority(values: Iterable[str]) -> tuple[str, int]:
    """Give the commonest value and how often it occurs, or `NOTHING_SCORED` and 0."""
    counted = Counter(values).most_common(1)
    return counted[0] if counted else (NOTHING_SCORED, 0)


def wilson(hits: int, sample: int) -> tuple[float, float]:
    """Give the 95% Wilson interval of a rate, refusing a sample of nothing."""
    if sample <= 0:
        raise ValueError("an empty sample has no interval")
    rate = hits / sample
    spread = Z * Z / sample
    centre = (rate + spread / 2) / (1 + spread)
    half = Z * sqrt(rate * (1 - rate) / sample + spread / (4 * sample)) / (1 + spread)
    return centre - half, centre + half


def member_measures(outcomes: tuple[CouncilOutcome, ...]) -> tuple[MemberMeasure, ...]:
    """Measure what each member said on each metric, across every item of one roster."""
    rulings = chain.from_iterable(outcome.rulings for outcome in outcomes)
    spoken = list(chain.from_iterable(said_in(ruling) for ruling in rulings))
    members = list(dict.fromkeys(said.member.name for _, said in spoken))
    pairs = product(members, METRIC_ORDER)
    return tuple(member_measure(member, metric, spoken) for member, metric in pairs)


def said_in(ruling: MetricRuling) -> list[tuple[str, MemberSaid]]:
    """Give every member's word on one ruling, with the metric it was about."""
    return [(ruling.metric, said) for said in ruling.said]


def member_measure(member: str, metric: str, spoken: list[tuple[str, MemberSaid]]) -> MemberMeasure:
    """Count one member's kinds of reply on one metric, and the values it named."""
    own = [said for asked, said in spoken if asked == metric and said.member.name == member]
    kinds = dict(Counter(kind_of(said) for said in own))
    named = tuple(sorted({said.value for said in own if said.value}))
    return MemberMeasure(member, metric, kinds, named)


def kind_of(said: MemberSaid) -> str:
    """Name what a member did, telling a quotation that verified from one that did not."""
    if said.kind is not SaidKind.ANSWERED:
        return said.kind.value
    return VERIFIED if said.verified else NOT_IN_ADVISORY


def outcome_totals(outcomes: tuple[CouncilOutcome, ...]) -> Counter:
    """Count every metric of every item by what the chairman made of it."""
    rulings = chain.from_iterable(outcome.rulings for outcome in outcomes)
    return Counter(ruling.outcome.value for ruling in rulings)
