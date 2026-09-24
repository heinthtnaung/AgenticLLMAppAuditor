"""A record a run left nothing out of, built by the code that builds it in a run.

`not_assessed` empties only when the organisation's answers weighed a finding,
somebody approved the audit, and a council read at least one advisory. Each is
made here the way a run makes it -- the council is the real chairman in
`council_runs`, the finding is weighed by `cli.organisation_run` against the
vector that council settled, and the approval is the type an answer file is
read into -- rather than by handing a renderer an empty tuple, which is a record
no run can produce.

Named `full_runs` and not `samples`: pytest puts each test directory on the path
and imports by basename.
"""

from cli.organisation_run import weigh_findings
from council_runs import council_ran
from organisation.answers import OrganisationAnswers
from organisation.approval import Approval, Decision
from report.record import Coverage, Report, build_report
from report_samples import PROVENANCE, catalogue, component, finding
from scoring.library import APPROVED_QUESTIONS
from scoring.question import Answer

ADVISORY_ID = "CVE-2019-14234"
EVERYWHERE_NO = OrganisationAnswers(
    everywhere={asked.question_id: Answer.NO for asked in APPROVED_QUESTIONS}
)
APPROVED = Approval("hein", Decision.APPROVED, "2026-09-23T09:15:00Z", "reviewed on staging")


def fully_assessed(coverage: Coverage = Coverage()) -> Report:
    """Build a record whose answers were weighed, which was approved, and which a council read."""
    installed = component()
    one = finding(installed, advisory_id=ADVISORY_ID)
    settled = council_ran(ADVISORY_ID)
    return build_report(
        PROVENANCE,
        catalogue(installed),
        (one,),
        {},
        council=(settled,),
        risk=weigh_findings((one,), EVERYWHERE_NO, {ADVISORY_ID: settled}),
        approval=APPROVED,
        coverage=coverage,
    )
