"""Records the approval tests read: a finding for each half of the rule, and one that needs none.

Named `approval_runs` and not `samples`: pytest puts each test directory on the
path and imports by basename.
"""

from organisation.approval import Approval, Decision
from organisation.risk import assess, per_source
from report.absences import Coverage
from report.record import Report, build_report
from report_samples import (
    HARMLESS, LOW_CONFIDENTIALITY, PROVENANCE, TOTAL_LOSS, catalogue, component, finding,
)
from scoring.library import APPROVED_QUESTIONS
from scoring.question import Answer

DJANGO = component()
PYYAML = component("pyyaml", "5.1")
FLASK = component("flask", "1.0")

# Measured against the vectors below: exposed and in production, TOTAL_LOSS comes
# out 65.65 High and HARMLESS 36.25 Medium; with every answer No, 29.4 Medium
# and 0.0 Low.
UNEXPOSED = {asked.question_id: Answer.NO for asked in APPROVED_QUESTIONS}
EXPOSED = {
    **UNEXPOSED,
    **{one: Answer.YES for one in ("EXP-1", "EXP-2", "EXP-3", "BUS-1", "BUS-2")},
}

DISPUTED = finding(DJANGO, vectors={"ghsa": TOTAL_LOSS, "nvd": LOW_CONFIDENTIALITY})
SEVERE = finding(PYYAML, advisory_id="CVE-2020-14343", vectors={"ghsa": TOTAL_LOSS})
QUIET = finding(FLASK, advisory_id="CVE-2023-30861", vectors={"ghsa": HARMLESS})
EVERY_KIND = (DISPUTED, SEVERE, QUIET)

APPROVED = Approval("hein", Decision.APPROVED, "2026-09-23T09:15:00Z")


def approval_report(answers=None, approval=None, findings=EVERY_KIND) -> Report:
    """Build a record of these findings, weighed against the answers when there are any."""
    return build_report(
        PROVENANCE,
        catalogue(DJANGO, PYYAML, FLASK),
        findings,
        {},
        risk=weighed(findings, answers),
        approval=approval,
        coverage=Coverage(answers_given=answers is not None),
    )


def weighed(findings, answers) -> tuple:
    """Weigh every finding against the answers, or none when nobody answered."""
    if answers is None:
        return ()
    return tuple(assess(one, answers, per_source(one)) for one in findings)
