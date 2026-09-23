"""Weighing every finding against this environment, when an operator supplied answers.

**Without answers there is no Organisation Risk Score and the report says so.**
Scoring an unanswered environment would put a number on a question nobody asked,
and a 0 printed there reads as a finding assessed and found harmless.

Where a council settled a vector there is one agreed technical severity, so that
finding gets one score. Everywhere else it is scored once per source, because
choosing one source is the precedence `docs/SCORING_MODEL.md` leaves open.
"""

from pathlib import Path
from typing import Iterable, Mapping

from findings.finding import Finding
from organisation.answers import OrganisationAnswers, approval_block, read_answers
from organisation.approval import Approval, ApprovalOutcome, NotApproved, read_decision
from organisation.risk import FindingRisk, assess, from_council, per_source
from report.council_record import CouncilAssessment, CouncilOutcome

NO_ANSWER_FILE = "no answer file was given, so nobody was asked about this environment"


def weigh_findings(
    findings: Iterable[Finding],
    answers: OrganisationAnswers,
    council: Mapping[str, CouncilOutcome],
) -> tuple[FindingRisk, ...]:
    """Score every finding against the answers that apply to it."""
    return tuple(
        assess(
            finding,
            answers.applying_to(finding.advisory.advisory_id),
            technical_for(finding, council),
        )
        for finding in findings
    )


def technical_for(finding: Finding, council: Mapping[str, CouncilOutcome]):
    """Give the technical severities one finding offers: the council's, or every source's."""
    settled = council.get(finding.advisory.advisory_id)
    if isinstance(settled, CouncilAssessment):
        return from_council(settled.vector)
    return per_source(finding)


def read_approval(path: Path) -> ApprovalOutcome:
    """Read the approval an answer file carries, which is usually none."""
    block = approval_block(path)
    if not block:
        return NotApproved("the answer file carries no approval")
    return Approval(
        approver=str(block.get("approver") or ""),
        decision=read_decision(block.get("decision") or ""),
        recorded_at=str(block.get("recorded_at") or ""),
        note=str(block.get("note") or ""),
    )


def organisation_of(path: Path | None) -> tuple[OrganisationAnswers, ApprovalOutcome]:
    """Read what the organisation said, or record that it said nothing."""
    if path is None:
        return OrganisationAnswers(), NotApproved(NO_ANSWER_FILE)
    return read_answers(path), read_approval(path)
