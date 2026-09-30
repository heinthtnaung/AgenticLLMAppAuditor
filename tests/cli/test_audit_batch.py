"""Guards on an audit run in the batch order: the record and all three reports, byte for byte.

The batch -- every council, then every escalation -- changes when each call is
made, so the same replies have to give the same record, and the same text, JSON
and page, as asking one finding at a time did. Whether a live model gives the same
replies in both orders is not something stand-in replies can show.
"""

import io

from cli import audit as audit_module
from cli.arguments import TEXT_FORMAT, Options
from cli.audit import run_audit
from cli.council_run import assessments
from council.ruling import Basis
from report.html_report import as_html
from report.json_report import as_json
from report.text_report import as_text
from batch_samples import ADVISORIES, BIG, answering, one_finding_at_a_time
from cli_samples import DATED, LODASH, explaining_nothing, scanners_answering

RENDERERS = (as_text, as_json, as_html)


def audited(tmp_path, monkeypatch, assessing) -> tuple:
    """Run one audit whose council assesses as `assessing` does, giving the record and stderr."""
    scanners_answering(monkeypatch, advisories={LODASH.purl: ADVISORIES})
    explaining_nothing(monkeypatch)
    monkeypatch.setenv("AUDITOR_ESCALATION_MODEL", BIG)

    def stand_in(findings, roster, progress, every_finding, escalation):
        """Assess with the batch tests' replies instead of the models on this machine."""
        clients = answering([])
        return assessing(
            findings, roster, clients, progress, every_finding=every_finding, escalation=escalation
        )

    monkeypatch.setattr(audit_module, "assessments", stand_in)
    council = ("small", "other")
    options = Options(repository=tmp_path, report_format=TEXT_FORMAT, council_models=council)
    progress = io.StringIO()
    return run_audit(options, DATED, progress), progress.getvalue()


def test_the_record_and_every_report_are_byte_identical_to_asking_one_finding_at_a_time(
    tmp_path, monkeypatch
):
    batch, _ = audited(tmp_path, monkeypatch, assessments)
    turn, _ = audited(tmp_path, monkeypatch, one_finding_at_a_time)
    assert batch == turn
    assert [render(batch) for render in RENDERERS] == [render(turn) for render in RENDERERS]
    escalated = {one.metric: one.basis for one in batch.council["CVE-OPEN-S"].rulings}["S"]
    assert escalated == Basis.ESCALATED.value


def test_the_progress_stream_holds_the_same_lines_in_another_order(tmp_path, monkeypatch):
    _, batch = audited(tmp_path, monkeypatch, assessments)
    _, turn = audited(tmp_path, monkeypatch, one_finding_at_a_time)
    assert batch != turn
    assert sorted(batch.splitlines()) == sorted(turn.splitlines())
