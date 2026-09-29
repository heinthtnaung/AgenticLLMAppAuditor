"""What a council's cross-check was worth on each metric: settled alone, and contests that caught.

**A value one member quoted alone was not cross-checked**, whatever else the
other members did, and the record says so with the `SOLE` basis. Counting them
answers what `measurements/README.md` says the recorded reports cannot: how many
of a roster's settled values rest on one member.

**A contest is worth something when it catches an error.** Where R1 has a value
for a contested metric, the contest caught one if R1's value is among the
verified candidates -- a member read it right and another did not, and the
disagreement stopped the wrong one reaching a vector. Where R1's value is
among none of them, every member that quoted was wrong, and the contest
caught nothing but a disagreement between two wrong readings.
"""

from dataclasses import dataclass
from typing import Mapping

from council.ruling import Basis
from cvss.metrics import METRIC_ORDER
from report.council_record import CouncilOutcome, MetricRuling, Outcome, SaidKind

from council_eval.dataset import Item
from council_eval.measures import ruling_for
from council_eval.reference import r1_reference


@dataclass(frozen=True)
class ContestMeasure:
    """One metric's cross-checking: settled on one quotation alone, and contests R1 can judge."""

    metric: str
    settled: int
    sole: int
    contested: int
    contested_referenced: int
    caught: int


def contest_measures(
    items: tuple[Item, ...], outcomes: tuple[CouncilOutcome, ...]
) -> tuple[ContestMeasure, ...]:
    """Measure the cross-check on every metric of one roster's outcomes."""
    references = {item.key: r1_reference(item.finding.advisory.vectors) for item in items}
    return tuple(contest_measure(metric, outcomes, references) for metric in METRIC_ORDER)


def contest_measure(
    metric: str,
    outcomes: tuple[CouncilOutcome, ...],
    references: Mapping[str, Mapping[str, str]],
) -> ContestMeasure:
    """Count one metric's lone settlements, and its contests that R1 can judge and that caught."""
    rulings = [(one.advisory_id, ruling_for(one, metric)) for one in outcomes]
    settled = [ruling for _, ruling in rulings if ruling.outcome is Outcome.SETTLED]
    contested = [(key, ruling) for key, ruling in rulings if ruling.outcome is Outcome.CONTESTED]
    judgeable = [(key, ruling) for key, ruling in contested if metric in references[key]]
    judged = [(references[key][metric], ruling) for key, ruling in judgeable]
    return ContestMeasure(
        metric=metric,
        settled=len(settled),
        sole=sum(ruling.basis == Basis.SOLE.value for ruling in settled),
        contested=len(contested),
        contested_referenced=len(judged),
        caught=sum(reference in verified_values(ruling) for reference, ruling in judged),
    )


def verified_values(ruling: MetricRuling) -> set[str]:
    """Give the values members supported with a quotation the advisory contains."""
    return {said.value for said in ruling.said if said.kind is SaidKind.ANSWERED and said.verified}
