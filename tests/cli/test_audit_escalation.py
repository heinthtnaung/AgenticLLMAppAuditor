"""Guards on escalation in an audit: read only for a council, and never reaching the score.

`docs/SCORING_MODEL.md`: the score reads no council's vector, whatever the
roster. A vector escalation completed is still a council's vector.
"""

import json

import pytest

from cli import audit as audit_module
from cli.arguments import TEXT_FORMAT, Options
from cli.audit import run_audit
from cli.council_run import assess_one, escalation_member
from council.env_file import SettingsError
from council.ruling import Basis
from report.council_record import CouncilAssessment
from cli_samples import (
    ADVISORY,
    DATED,
    QUOTATION,
    advisory_like,
    scanners_answering,
    written_answers,
)

BIG = "big:27b"
# A reading far below both published ones, 9.8 and 5.3, and the council declines
# S, which only the escalation model reads: the vector exists only because of it.
FAR_FROM_PUBLISHED = {
    "AV": "P", "AC": "H", "PR": "H", "UI": "R", "S": "C", "C": "L", "I": "N", "A": "N",
}
UNSCORED = advisory_like("CVE-UNSCORED", vectors={})


def options_for(path, models=(), answers=None) -> Options:
    """Build the options one run is about."""
    return Options(
        repository=path, report_format=TEXT_FORMAT, council_models=tuple(models), answers=answers
    )


def said(member, prompt) -> str:
    """Answer from the table, quoting the advisory; the council declines S, the model reads it."""
    if prompt.metric == "S" and member.name != BIG:
        return json.dumps({"value": "NO_EVIDENCE", "evidence": ""})
    value = FAR_FROM_PUBLISHED[prompt.metric]
    return json.dumps({"value": value, "evidence": QUOTATION, "confidence": "high"})


def escalating_far_from_published(findings, roster, **_):
    """Stand in for the council run with the real one and escalation, reading every metric low."""
    escalation = escalation_member(BIG)
    clients = {"ollama": said}
    return tuple(assess_one(one, roster, clients, escalation=escalation) for one in findings)


@pytest.mark.parametrize(
    ("advisory", "provisional"), [(ADVISORY, False), (UNSCORED, True)],
    ids=["published sources scored it", "no source scored it"],
)
def test_a_vector_escalation_completed_never_moves_the_organisation_risk_score(
    tmp_path, monkeypatch, advisory, provisional
):
    scanners_answering(monkeypatch, advisories={advisory.purl: (advisory,)})
    monkeypatch.setattr(audit_module, "assessments", escalating_far_from_published)
    answers = written_answers(tmp_path)
    beside = run_audit(options_for(tmp_path, ("small",), answers), DATED)
    alone = run_audit(options_for(tmp_path, answers=answers), DATED)
    council = beside.council[advisory.advisory_id]
    assert isinstance(council, CouncilAssessment)
    assert {one.metric: one.basis for one in council.rulings}["S"] == Basis.ESCALATED.value
    assert beside.risk == alone.risk
    assert beside.risk[advisory.advisory_id].is_provisional is provisional


def escalations_asked(asked: list):
    """Stand in for the council run, keeping the escalation model each run was given."""

    def assessments(findings, roster, **options):
        """Note the escalation, and ask nobody."""
        asked.append(options["escalation"])
        return ()

    return assessments


def test_with_the_setting_unset_a_council_run_escalates_nothing_and_says_so(tmp_path, monkeypatch):
    asked = []
    scanners_answering(monkeypatch)
    monkeypatch.setattr(audit_module, "assessments", escalations_asked(asked))
    report = run_audit(options_for(tmp_path, ("small",)), DATED)
    assert asked == [None]
    assert report.provenance.local_models.escalation_model is None


def test_the_setting_names_the_local_model_a_council_run_escalates_to(tmp_path, monkeypatch):
    asked = []
    scanners_answering(monkeypatch)
    monkeypatch.setenv("AUDITOR_ESCALATION_MODEL", BIG)
    monkeypatch.setattr(audit_module, "assessments", escalations_asked(asked))
    report = run_audit(options_for(tmp_path, ("small",)), DATED)
    assert asked == [escalation_member(BIG)]
    assert asked[0].runs_local
    assert report.provenance.local_models.escalation_model == BIG


def test_the_setting_is_read_only_for_a_council_and_a_bad_one_stops_it_before_the_scan(
    tmp_path, monkeypatch
):
    def scanned(path) -> None:
        """Fail the test: nothing should be scanned once a setting is refused."""
        raise AssertionError("the repository was scanned")

    scanners_answering(monkeypatch)
    monkeypatch.setenv("AUDITOR_ESCALATION_MODEL", "big:27b,other:70b")
    assert run_audit(options_for(tmp_path), DATED).provenance.local_models is None
    monkeypatch.setattr(audit_module.syft_runner, "scan_directory", scanned)
    with pytest.raises(SettingsError, match="names one model"):
        run_audit(options_for(tmp_path, ("small",)), DATED)
