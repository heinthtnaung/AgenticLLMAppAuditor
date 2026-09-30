"""What one council run comes to in the record: a vector, or the metrics it could not settle.

**A council that leaves any metric open produces no vector**, open meaning still
contested or unresolved once any escalation has been made. With no fallback
offered (`cli.council_run.FALLBACKS`), an unsettled metric has no value, and a
partial vector is not something the engine may be handed, so the finding's
published scores stand side by side with no council reading beside them. The
vector is discarded; **the fact that a council ran is not**, and neither is what
it could not settle -- a record without it would say no council had run at all.
"""

from cli.council_detail import nothing_cross_checked
from council.chairman import agreed_vector
from council.ruling import ContestedMetric, UnresolvedMetric
from council.run import CouncilRun
from cvss.metrics import METRIC_ORDER
from findings.finding import Finding
from report.council_record import (
    CouncilAssessment,
    CouncilOutcome,
    CouncilWithoutVector,
    MetricRuling,
)

VECTOR_VERSION = "3.1"


def outcome_of(
    finding: Finding, run: CouncilRun, rulings: tuple[MetricRuling, ...]
) -> CouncilOutcome:
    """Record what one council run reached: a vector, or the metrics it could not settle."""
    unresolved = metrics_of(run, UnresolvedMetric)
    contested = metrics_of(run, ContestedMetric)
    if unresolved or contested:
        # The run is still recorded: it happened, and what it could not settle is the result.
        return CouncilWithoutVector(
            advisory_id=finding.advisory.advisory_id,
            single_assessor=run.single_assessor,
            unresolved_metrics=unresolved,
            contested_metrics=contested,
            rulings=rulings,
        )
    return CouncilAssessment(
        advisory_id=finding.advisory.advisory_id,
        vector=str(agreed_vector(run.rulings, VECTOR_VERSION)),
        single_assessor=run.single_assessor,
        rulings=rulings,
        nothing_cross_checked=nothing_cross_checked(run),
    )


def metrics_of(run: CouncilRun, kind: type) -> tuple[str, ...]:
    """Name the metrics a run left in one state, in specification order."""
    return tuple(
        metric for metric in METRIC_ORDER if isinstance(run.rulings.get(metric), kind)
    )
