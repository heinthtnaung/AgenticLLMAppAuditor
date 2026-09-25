"""Guards on the pipeline: the packages wired in the right order, and asked for the truth."""

import json

import pytest

from cli import audit as audit_module
from cli.arguments import Options, TEXT_FORMAT
from cli.audit import run_audit
from cli.council_run import assess_one
from report.council_record import CouncilAssessment
from scoring.library import APPROVED_QUESTIONS
from cli_samples import (
    ADVISORY,
    BUILT_AT,
    DATED,
    LODASH,
    QUOTATION,
    SYFT_VERSION,
    TRIVY_VERSION,
    advisory_like,
    scanners_answering,
    written_answers,
)

# A reading far below both published ones, 9.8 and 5.3, so a council vector
# weighed into the score in any way at all would move a number.
FAR_FROM_PUBLISHED = {
    "AV": "P", "AC": "H", "PR": "H", "UI": "R", "S": "U", "C": "L", "I": "N", "A": "N",
}
# An advisory no source published a vector for, which the council can still read.
UNSCORED = advisory_like("CVE-UNSCORED", vectors={})


def options_for(path, models=(), answers=None) -> Options:
    """Build the options one run is about."""
    return Options(
        repository=path, report_format=TEXT_FORMAT, council_models=tuple(models), answers=answers
    )


def test_an_audit_joins_what_is_installed_to_what_is_published(tmp_path, monkeypatch):
    scanners_answering(monkeypatch)
    report = run_audit(options_for(tmp_path), DATED)
    assert len(report.findings) == 1
    assert report.findings[0].advisory.advisory_id == ADVISORY.advisory_id
    assert [score.source for score in report.findings[0].scores] == ["ghsa", "nvd"]


def test_the_versions_are_asked_of_the_tools_and_not_configured(tmp_path, monkeypatch):
    # A field somebody types is a claim nobody checked, and this field exists to
    # make a run checkable. The tool printed trivy 0.58.1 on a 0.74.0 machine
    # for exactly as long as a person supplied the number.
    scanners_answering(monkeypatch)
    provenance = run_audit(options_for(tmp_path), DATED).provenance
    assert (provenance.syft_version, provenance.trivy_version) == (SYFT_VERSION, TRIVY_VERSION)


def test_the_scan_reads_the_cache_the_preflight_dated(tmp_path, monkeypatch):
    # The database dated is the database scanned, which holds only if the scan
    # is handed the very cache the date was read from.
    scanners_answering(monkeypatch)
    handed = []

    def scanning(path, cache):
        """Record the cache the scan was handed, and answer as Trivy would."""
        handed.append(cache)
        return {ADVISORY.purl: (ADVISORY,)}

    monkeypatch.setattr(audit_module.trivy_runner, "scan_directory", scanning)
    run_audit(options_for(tmp_path), DATED)
    assert handed == [DATED.cache]


def test_the_run_records_the_repository_it_was_given(tmp_path, monkeypatch):
    scanners_answering(monkeypatch)
    assert run_audit(options_for(tmp_path), DATED).provenance.repository == str(tmp_path)


def test_the_database_date_the_preflight_read_is_what_the_record_carries(tmp_path, monkeypatch):
    scanners_answering(monkeypatch)
    assert run_audit(options_for(tmp_path), DATED).provenance.database.built_at == BUILT_AT


def test_a_component_nothing_was_published_against_is_counted(tmp_path, monkeypatch):
    clean = LODASH.__class__(
        name="left-pad", version="1.3.0", purl="pkg:npm/left-pad@1.3.0",
        ecosystem="npm", locations=("/package-lock.json",),
    )
    scanners_answering(monkeypatch, components=(LODASH, clean))
    report = run_audit(options_for(tmp_path), DATED)
    assert report.component_count == 2
    assert report.components_without_findings == (clean.purl,)


def test_a_repository_with_nothing_in_it_is_a_run_that_found_nothing(tmp_path, monkeypatch):
    scanners_answering(monkeypatch, components=(), advisories={})
    report = run_audit(options_for(tmp_path), DATED)
    assert report.findings == ()
    assert report.component_count == 0


def test_no_council_runs_unless_the_operator_named_one(tmp_path, monkeypatch):
    scanners_answering(monkeypatch)
    report = run_audit(options_for(tmp_path), DATED)
    assert report.council == {}
    assert "Council ruling" in [absence.what for absence in report.not_assessed]


def test_the_same_scan_builds_the_same_record(tmp_path, monkeypatch):
    scanners_answering(monkeypatch)
    assert run_audit(options_for(tmp_path), DATED) == run_audit(options_for(tmp_path), DATED)


def test_the_advisories_an_answer_file_overrides_reach_the_record(tmp_path, monkeypatch):
    # A mistyped advisory id applies to nothing; the run keeps going and the
    # report says which override matched no finding.
    scanners_answering(monkeypatch)
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({
        "answers": {asked.question_id: "No" for asked in APPROVED_QUESTIONS},
        "by_advisory": {"CVE-NOT-FOUND": {"THR-1": "Yes"}},
    }), encoding="utf-8")
    report = run_audit(options_for(tmp_path, answers=answers), DATED)
    assert report.overrides_without_findings == ("CVE-NOT-FOUND",)
    assert len(report.findings) == 1


def settling_far_from_published(findings, roster, clients=None, progress=None, every_finding=False):
    """Stand in for a council run with the real one, its members reading every metric low."""
    def said(member, prompt):
        """Answer one metric from the table, quoting the advisory so the quotation verifies."""
        value = FAR_FROM_PUBLISHED[prompt.metric]
        return json.dumps({"value": value, "evidence": QUOTATION, "confidence": "high"})

    return tuple(assess_one(one, roster, {"ollama": said}) for one in findings)


@pytest.mark.parametrize(
    ("advisory", "provisional"), [(ADVISORY, False), (UNSCORED, True)],
    ids=["published sources scored it", "no source scored it"],
)
def test_a_councils_settled_vector_never_moves_the_organisation_risk_score(
    tmp_path, monkeypatch, advisory, provisional
):
    # The pilot on vulnscout found the council's settled values off the reference,
    # and the ruling was that its vector sits beside the published scores and is
    # never weighed. Anything reading it into a score makes these two differ.
    # The accepted cost: a finding no source scored keeps technical severity at 0
    # and stays provisional, though a council settled a vector for it.
    scanners_answering(monkeypatch, advisories={advisory.purl: (advisory,)})
    monkeypatch.setattr(audit_module, "assessments", settling_far_from_published)
    answers = written_answers(tmp_path)
    beside = run_audit(options_for(tmp_path, ("small",), answers), DATED)
    alone = run_audit(options_for(tmp_path, answers=answers), DATED)
    assert isinstance(beside.council[advisory.advisory_id], CouncilAssessment)
    assert beside.risk == alone.risk
    assert beside.risk[advisory.advisory_id].is_provisional is provisional
