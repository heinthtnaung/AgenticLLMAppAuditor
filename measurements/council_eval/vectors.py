"""Each vector a roster handed over, beside R1 and beside every score the sources published.

A vector is where the council's readings become a number. What is kept per
vector is how that number compares with the ones already published: the score
and band the engine gives it, the metrics where it departs from R1, and the
scores each source published, so a reader sees whether it landed inside their
range or outside all of them.

Every number is `src/cvss/score.py`'s, from the vector beside it.
"""

from dataclasses import dataclass
from typing import Mapping

from cvss.metrics import METRIC_ORDER
from cvss.score import base_score, severity_band
from cvss.vector import parse
from report.council_record import CouncilAssessment, CouncilOutcome

from council_eval.dataset import Item
from council_eval.reference import NO_FULL_REFERENCE, full_reference, r1_reference


@dataclass(frozen=True)
class VectorMeasure:
    """One vector a roster reached, what the engine makes of it, and where it departs from R1."""

    key: str
    vector: str
    score: float
    band: str
    referenced: int
    departs_on: tuple[str, ...]
    reference: str
    published: Mapping[str, float]

    @property
    def inside_published_range(self) -> bool:
        """Say whether the score lies between the lowest and highest a source published."""
        scores = self.published.values()
        return bool(scores) and min(scores) <= self.score <= max(scores)


def vector_measures(
    items: tuple[Item, ...], outcomes: tuple[CouncilOutcome, ...]
) -> tuple[VectorMeasure, ...]:
    """Measure every vector the roster reached, in the order of the items."""
    by_key = {item.key: item for item in items}
    reached = [one for one in outcomes if isinstance(one, CouncilAssessment)]
    return tuple(vector_measure(one, by_key[one.advisory_id]) for one in reached)


def vector_measure(outcome: CouncilAssessment, item: Item) -> VectorMeasure:
    """Score one council vector and set it against R1 and the published scores."""
    parsed = parse(outcome.vector)
    reference = r1_reference(item.finding.advisory.vectors)
    score = base_score(parsed)
    return VectorMeasure(
        key=item.key,
        vector=outcome.vector,
        score=score,
        band=severity_band(score),
        referenced=len(reference),
        departs_on=departures(parsed.metrics, reference),
        reference=full_reference(item.finding.advisory.vectors),
        published={one.source: one.base_score for one in item.finding.scores},
    )


def departures(metrics: Mapping[str, str], reference: Mapping[str, str]) -> tuple[str, ...]:
    """Name the metrics R1 references where the council's value is another."""
    referenced = [metric for metric in METRIC_ORDER if metric in reference]
    return tuple(metric for metric in referenced if metrics[metric] != reference[metric])


def reference_band(measure: VectorMeasure) -> str:
    """Give the band of the R1 vector, or `NO_FULL_REFERENCE` where R1 lacks a metric."""
    if measure.reference == NO_FULL_REFERENCE:
        return NO_FULL_REFERENCE
    return severity_band(base_score(parse(measure.reference)))
