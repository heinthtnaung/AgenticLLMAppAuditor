"""Which findings need a human's approval: one deterministic rule, and the reason for each half.

An approval is recorded once per audit, in the answer file (`organisation.approval`).
This says which findings that approval is *for*, so a report can say plainly
when some need one and none was given. It reads the record and nothing else --
no model, no clock -- so the same record marks the same findings every time.

**A High or Critical Organisation Risk Score needs a human.** Those are the top
two bands of this system's own score, where a finding matters in this
environment and not only in general, and what to do about one is a risk
decision `docs/SCORING_MODEL.md` keeps from the council. Any source's score
counts, not only the lowest: a finding is scored once per source because
choosing one is the precedence the design leaves open, so a High from any of
them is a High somebody has to own.

**Published sources that disagree need a human.** A metric two sources read
differently is a conflict nobody has resolved, and nothing in this tool may
resolve it: the published scores stand side by side and a council's reading
only stands beside them.

Without organisation answers there is no risk score, so only the second half
can mark a finding; the report says so where it gives the count.
"""

from enum import Enum

from findings.finding import Finding
from organisation.risk import FindingRisk

# The organisation bands that need a human, named as `scoring.bands` names them.
APPROVAL_BANDS = ("Critical", "High")


class ApprovalReason(Enum):
    """Why a finding needs approval, in the words every rendering gives it."""

    RISK_BAND = "a High or Critical Organisation Risk Score"
    SOURCES_DISAGREE = "sources that disagree"


def approval_reasons(
    finding: Finding, weighed: FindingRisk | None
) -> tuple[ApprovalReason, ...]:
    """Name each half of the rule a finding meets, in the rule's order; none if it needs none."""
    refuse_another_findings_risk(finding, weighed)
    reasons = []
    if weighed is not None and any(band in APPROVAL_BANDS for band in weighed.bands):
        reasons.append(ApprovalReason.RISK_BAND)
    if finding.disputed_metrics():
        reasons.append(ApprovalReason.SOURCES_DISAGREE)
    return tuple(reasons)


def refuse_another_findings_risk(finding: Finding, weighed: FindingRisk | None) -> None:
    """Refuse a risk score weighed for some other advisory, which would mark the wrong finding."""
    if weighed is None or weighed.advisory_id == finding.advisory.advisory_id:
        return
    raise ValueError(
        f"The risk for {weighed.advisory_id} was paired with {finding.advisory.advisory_id}"
    )
