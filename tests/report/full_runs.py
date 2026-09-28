"""A record a run left nothing out of, built by the code that builds it in a run.

`not_assessed` empties only when the organisation's answers weighed a finding,
somebody approved the audit, a council read at least one advisory, and a model
explained why a finding's sources differ. Each is made here the way a run makes
it -- the council is the real chairman in `council_runs`, the finding is weighed
by `cli.organisation_run` from its published sources with that council's settled
vector beside it, the explanation is `cli.explanation_run` with the model's reply
from a table, and the approval is the type an answer file is read into -- rather
than by handing a renderer an empty tuple, which is a record no run can produce.

Named `full_runs` and not `samples`: pytest puts each test directory on the path
and imports by basename.
"""

import json

from cli.council_run import local_member
from cli.explanation_run import explanations
from cli.organisation_run import weigh_findings
from council_runs import council_ran
from organisation.answers import OrganisationAnswers
from organisation.approval import Approval, Decision
from report.absences import Coverage
from report.record import Report, build_report
from report_samples import (
    CONFIDENTIALITY_ONLY,
    LOW_CONFIDENTIALITY,
    PROVENANCE,
    catalogue,
    component,
    finding,
)
from scoring.library import APPROVED_QUESTIONS
from scoring.question import Answer

ADVISORY_ID = "CVE-2019-14234"
EVERYWHERE_NO = OrganisationAnswers(
    everywhere={asked.question_id: Answer.NO for asked in APPROVED_QUESTIONS}
)
APPROVED = Approval("hein", Decision.APPROVED, "2026-09-23T09:15:00Z", "reviewed on staging")
# Two sources reading confidentiality apart, so there is a disagreement to explain.
DISAGREEING = {"ghsa": CONFIDENTIALITY_ONLY, "nvd": LOW_CONFIDENTIALITY}
EXPLAINED_C = {"items": [
    {
        "metric": "C", "why": "It does not say what can be read.",
        "quotation": "An issue was discovered",
    }
]}


def explaining(member, prompt) -> str:
    """Answer the explainer's question from a table, quoting the advisory."""
    return json.dumps(EXPLAINED_C)


def fully_assessed(coverage: Coverage = Coverage()) -> Report:
    """Build a record whose answers were weighed, which was approved, and which a council read."""
    installed = component()
    one = finding(installed, advisory_id=ADVISORY_ID, vectors=DISAGREEING)
    settled = council_ran(ADVISORY_ID)
    return build_report(
        PROVENANCE,
        catalogue(installed),
        (one,),
        {},
        council=(settled,),
        risk=weigh_findings((one,), EVERYWHERE_NO),
        approval=APPROVED,
        coverage=coverage,
        explanations=explanations((one,), local_member("qwen2.5:7b"), {"ollama": explaining}),
    )
