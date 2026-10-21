"""The approval badge the Overview table and the finding cards both show for a flagged finding.

A finding the rule flags shows one badge, and which one depends on whether the
audit records an approval. None recorded is the alarm "needs approval"; a recorded
approval covers every flagged finding, so each shows the decision a human made --
"approved", or "overridden" where the human set the flag aside. One place, so the
table cell and the card cannot drift, and so each decision keeps its one tone.
"""

from organisation.approval import Approval, ApprovalOutcome, Decision
from report.approval_needed import NEEDS_APPROVAL

# What a recorded decision shows on a flagged finding, in the tone `report.html_style` colours.
DECISION_BADGES: dict[Decision, tuple[str, str]] = {
    Decision.APPROVED: ("approved", "ok"),
    Decision.OVERRIDDEN: ("overridden", "warn"),
}
# What a flagged finding shows when the audit records no approval at all.
UNAPPROVED_BADGE: tuple[str, str] = (NEEDS_APPROVAL, "alarm")


def approval_status(approval: ApprovalOutcome) -> tuple[str, str]:
    """Give the word and badge tone a flagged finding shows for this audit's approval decision."""
    if not isinstance(approval, Approval):
        return UNAPPROVED_BADGE
    return DECISION_BADGES[approval.decision]
