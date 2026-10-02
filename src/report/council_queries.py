"""Questions the report asks of a council's record: what it left open, whether it ran, what it flagged.

These read the projection in `report.council_record` and decide nothing new. They
live beside the record rather than in it, which leaves the record's file room for
new fields.
"""

from report.council_record import CouncilNotAsked, CouncilOutcome, MetricRuling, Outcome


def council_left_open(ruling: MetricRuling) -> bool:
    """Say whether the council itself left a metric open, whatever escalation made of it."""
    return ruling.outcome is not Outcome.SETTLED or ruling.escalation is not None


def was_assessed(outcome: CouncilOutcome) -> bool:
    """Say whether a council actually read this advisory, rather than passing over it."""
    return not isinstance(outcome, CouncilNotAsked)


def flagged_metrics(outcome: CouncilOutcome) -> tuple[str, ...]:
    """Name the metrics members read two ways from the same words, off the record's rulings."""
    if isinstance(outcome, CouncilNotAsked):
        return ()
    return tuple(one.metric for one in outcome.rulings if one.same_evidence_different_reading)
