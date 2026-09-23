"""Guards on the pipeline: the packages wired in the right order, and asked for the truth."""

from cli.arguments import Options, TEXT_FORMAT
from cli.audit import run_audit
from scoring.library import APPROVED_QUESTIONS
from cli_samples import (
    ADVISORY,
    BUILT_AT,
    LODASH,
    SYFT_VERSION,
    TRIVY_VERSION,
    scanners_answering,
)


def options_for(path, models=(), answers=None) -> Options:
    """Build the options one run is about."""
    return Options(
        repository=path, report_format=TEXT_FORMAT, council_models=tuple(models), answers=answers
    )


def test_an_audit_joins_what_is_installed_to_what_is_published(tmp_path, monkeypatch):
    scanners_answering(monkeypatch)
    report = run_audit(options_for(tmp_path), BUILT_AT)
    assert len(report.findings) == 1
    assert report.findings[0].advisory.advisory_id == ADVISORY.advisory_id
    assert [score.source for score in report.findings[0].scores] == ["ghsa", "nvd"]


def test_the_versions_are_asked_of_the_tools_and_not_configured(tmp_path, monkeypatch):
    # A field somebody types is a claim nobody checked, and this field exists to
    # make a run checkable. The tool printed trivy 0.58.1 on a 0.74.0 machine
    # for exactly as long as a person supplied the number.
    scanners_answering(monkeypatch)
    provenance = run_audit(options_for(tmp_path), BUILT_AT).provenance
    assert (provenance.syft_version, provenance.trivy_version) == (SYFT_VERSION, TRIVY_VERSION)


def test_the_run_records_the_repository_it_was_given(tmp_path, monkeypatch):
    scanners_answering(monkeypatch)
    assert run_audit(options_for(tmp_path), BUILT_AT).provenance.repository == str(tmp_path)


def test_the_database_date_the_preflight_read_is_what_the_record_carries(tmp_path, monkeypatch):
    scanners_answering(monkeypatch)
    assert run_audit(options_for(tmp_path), BUILT_AT).provenance.database.built_at == BUILT_AT


def test_a_component_nothing_was_published_against_is_counted(tmp_path, monkeypatch):
    clean = LODASH.__class__(
        name="left-pad", version="1.3.0", purl="pkg:npm/left-pad@1.3.0",
        ecosystem="npm", locations=("/package-lock.json",),
    )
    scanners_answering(monkeypatch, components=(LODASH, clean))
    report = run_audit(options_for(tmp_path), BUILT_AT)
    assert report.component_count == 2
    assert report.components_without_findings == (clean.purl,)


def test_a_repository_with_nothing_in_it_is_a_run_that_found_nothing(tmp_path, monkeypatch):
    scanners_answering(monkeypatch, components=(), advisories={})
    report = run_audit(options_for(tmp_path), BUILT_AT)
    assert report.findings == ()
    assert report.component_count == 0


def test_no_council_runs_unless_the_operator_named_one(tmp_path, monkeypatch):
    scanners_answering(monkeypatch)
    report = run_audit(options_for(tmp_path), BUILT_AT)
    assert report.council == {}
    assert "Council ruling" in [absence.what for absence in report.not_assessed]


def test_the_same_scan_builds_the_same_record(tmp_path, monkeypatch):
    scanners_answering(monkeypatch)
    assert run_audit(options_for(tmp_path), BUILT_AT) == run_audit(options_for(tmp_path), BUILT_AT)


def test_the_advisories_an_answer_file_overrides_reach_the_record(tmp_path, monkeypatch):
    # A mistyped advisory id applies to nothing; the run keeps going and the
    # report says which override matched no finding.
    import json

    scanners_answering(monkeypatch)
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({
        "answers": {asked.question_id: "No" for asked in APPROVED_QUESTIONS},
        "by_advisory": {"CVE-NOT-FOUND": {"THR-1": "Yes"}},
    }), encoding="utf-8")
    report = run_audit(options_for(tmp_path, answers=answers), BUILT_AT)
    assert report.overrides_without_findings == ("CVE-NOT-FOUND",)
    assert len(report.findings) == 1
