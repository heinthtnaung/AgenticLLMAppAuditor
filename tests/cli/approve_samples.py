"""The records and helpers the approve tests drive, without a scanner, a model or a socket.

Shared by `test_approve`, `test_approve_refusals` and `test_arguments_approve`, so the
record a decision is recorded on is built one way. The council, local models and
unidentified artifact are the projection types a run hands the report, built by hand
here: `built_rich` carries every field the JSON holds that no page renders, which is
what the gap test edits. Named `approve_samples`, not `samples`, because pytest puts
each test directory on the path and imports by basename.
"""

import io
import json
import os

import pytest

from cli.main import main
from cli_samples import ADVISORY, BUILT_AT, LODASH
from deps.syft_report import Catalogue, UnidentifiedArtifact
from deps.trivy_secrets import SecretFinding
from findings.finding import build_finding
from organisation.approval import Approval, Decision
from organisation.risk import assess, per_source
from report.council_record import (
    CouncilAssessment,
    MemberIdentity,
    MemberSaid,
    MetricRuling,
    Outcome,
    SaidKind,
)
from report.html_report import as_html
from report.json_report import as_json
from report.model_identity import MEMBER_ROLE, ModelDigest, OllamaVersion
from report.provenance import AdvisoryDatabase, LocalModels, RunProvenance
from report.record import Report, build_report
from report.text_report import as_text
from scoring.library import APPROVED_QUESTIONS
from scoring.question import Answer

RENDERERS = {".json": as_json, ".txt": as_text, ".html": as_html}
READ_ONLY = 0o400
OWNER_WRITE = 0o600
NEEDS_PERMISSIONS = pytest.mark.skipif(
    os.geteuid() == 0, reason="root writes anything, so no read-only file can be made"
)
PROVENANCE = RunProvenance(
    "fetched/vulnscout", "syft-under-test", "trivy-under-test", AdvisoryDatabase(BUILT_AT)
)
ANSWERS = {asked.question_id: Answer.NO for asked in APPROVED_QUESTIONS}
BLOCK = {"approver": "dana", "decision": "approved", "recorded_at": "2026-10-20T10:00:00Z"}
DECISION = Approval("dana", Decision.APPROVED, "2026-10-20T10:00:00Z", attached_after_run=True)

# A council, local models and an artifact, as the projection a run hands the report, so
# `built_rich` carries the fields the JSON holds and no page renders.
SETTLED_VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
MEMBER = MemberIdentity(
    "qwen2.5:7b", "ollama", "qwen2.5:7b", "qwen2.5", False, "member-base-metric-3"
)
SAID = MemberSaid(MEMBER, SaidKind.ANSWERED, "N", "a quoted sentence", "high", verified=True)
RULING = MetricRuling("AV", Outcome.SETTLED, (SAID,), value="N", basis="sole", confidence="high")
COUNCIL = CouncilAssessment(ADVISORY.advisory_id, SETTLED_VECTOR, False, (RULING,))
LOCAL_MODELS = LocalModels(
    server="http://127.0.0.1:11434", context_tokens=8192, timeout_seconds=180.0, temperature=0,
    seed=11, think=False, order_check=True, escalation_model=None,
    ollama_version=OllamaVersion("0.34.3"),
    models=(ModelDigest("qwen2.5:7b", MEMBER_ROLE, "845dbda0ea48"),),
)
WITH_MODELS = RunProvenance(
    "fetched/vulnscout", "syft-x", "trivy-x", AdvisoryDatabase(BUILT_AT), LOCAL_MODELS
)
ARTIFACT = UnidentifiedArtifact("./local-action", "github-action", ("/.github/",))


def built(approval) -> Report:
    """Build a record -- a disagreeing finding and a risk score -- approved or not."""
    one = build_finding(LODASH, ADVISORY)
    return build_report(
        PROVENANCE, Catalogue((LODASH,), ()), (one,), {},
        risk=[assess(one, ANSWERS, per_source(one))], approval=approval,
    )


def built_with_secret() -> Report:
    """Build an unapproved record carrying a secret, whose JSON has a line number to corrupt."""
    one = build_finding(LODASH, ADVISORY)
    secret = SecretFinding("config.py", 7, 7, "github-pat", "GitHub", "CRITICAL", "GitHub token")
    return build_report(PROVENANCE, Catalogue((LODASH,), ()), (one,), {}, secrets=(secret,))


def built_rich() -> Report:
    """Build an unapproved record with a council, local models and an artifact, for the gap test."""
    one = build_finding(LODASH, ADVISORY)
    return build_report(WITH_MODELS, Catalogue((LODASH,), (ARTIFACT,)), (one,), {}, (COUNCIL,))


def saved(folder, report: Report, name: str = "vulnscout"):
    """Write a record's three reports under the folder, and give the path of its JSON."""
    for suffix, render in RENDERERS.items():
        (folder / f"{name}{suffix}").write_text(render(report), encoding="utf-8")
    return folder / f"{name}.json"


def answers_at(folder, block):
    """Write an answers file carrying the given approval block, or none."""
    path = folder / "answers.json"
    path.write_text(json.dumps({"approval": block} if block else {}), encoding="utf-8")
    return path


def run(argv):
    """Run the command line, giving its exit code and what it wrote to each stream."""
    out, error = io.StringIO(), io.StringIO()
    code = main(argv, out=out, error=error)
    return code, out.getvalue(), error.getvalue()


def approve(folder, block=BLOCK, extra=()):
    """Approve the saved report in a folder from an answers file carrying a block."""
    report_json = saved(folder, built(None))
    argv = ["--approve", str(report_json), "--answers", str(answers_at(folder, block)), *extra]
    return (report_json, *run(argv))
