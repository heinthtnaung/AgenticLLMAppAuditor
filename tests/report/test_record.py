"""Guards on the record: what a run gathered, and what it is honest about not having."""

import pytest

from organisation.approval import Approval, Decision, NotApproved
from organisation.risk import assess, per_source
from report.provenance import AdvisoryDatabase, RunProvenance, UnknownAdvisoryDatabase
from report.council_record import CouncilAssessment
from report.record import Absence, Report, build_report
from scoring.library import APPROVED_QUESTIONS
from scoring.question import Answer
from report_samples import (
    DATABASE,
    PROVENANCE,
    TOTAL_LOSS,
    advisory,
    catalogue,
    component,
    finding,
    unidentified,
)

def all_answers(overrides=None) -> dict:
    """Answer every approved question No, except the ones a test names."""
    return {**{asked.question_id: Answer.NO for asked in APPROVED_QUESTIONS}, **(overrides or {})}


DJANGO = component()
PYYAML = component("pyyaml", "5.1")


def a_report(
    components=(), findings=(), advisories=None, council=(), unidentified=(),
    risk=(), approval=None, overridden=(),
):
    """Build one report from whatever a test is about."""
    found = catalogue(*components, unidentified=unidentified)
    return build_report(
        PROVENANCE, found, findings, advisories or {}, council, risk, approval, overridden
    )


def test_a_run_gathers_its_findings_and_counts_what_was_catalogued():
    report = a_report(components=(DJANGO, PYYAML), findings=(finding(DJANGO),))
    assert isinstance(report, Report)
    assert report.component_count == 2
    assert len(report.findings) == 1


def test_a_component_nothing_was_published_against_is_a_result():
    report = a_report(components=(DJANGO, PYYAML), findings=(finding(DJANGO),))
    assert report.components_without_findings == (PYYAML.purl,)


def test_an_advisory_matching_no_component_is_a_different_result():
    # A component with no advisory may really be clean. An advisory with no
    # component is a CVE that fell out of the join, and the report looks clean
    # either way -- so the two are counted apart.
    orphan = advisory(purl=PYYAML.purl)
    report = a_report(components=(DJANGO,), advisories={PYYAML.purl: (orphan,)})
    assert report.advisories_without_components == (PYYAML.purl,)
    assert report.components_without_findings == (DJANGO.purl,)


def test_the_two_kinds_of_nothing_are_both_sorted_so_two_runs_agree():
    report = a_report(components=(PYYAML, DJANGO))
    assert report.components_without_findings == tuple(sorted([DJANGO.purl, PYYAML.purl]))


@pytest.mark.parametrize("named", ["Organisation Risk Score", "Approval record"])
def test_what_this_build_cannot_assess_is_named_every_time(named):
    # Never 0 and never silently missing: a score printed as 0 reads as a
    # finding assessed and found harmless.
    assert named in [absence.what for absence in a_report().not_assessed]


def test_a_run_with_no_council_says_so():
    absences = {absence.what: absence.because for absence in a_report().not_assessed}
    assert "no source has been chosen between" in absences["Council ruling"]


def test_a_run_with_a_council_does_not_claim_it_had_none():
    settled = CouncilAssessment("CVE-2019-14234", TOTAL_LOSS, single_assessor=False)
    report = a_report(council=(settled,))
    assert "Council ruling" not in [absence.what for absence in report.not_assessed]
    assert report.council["CVE-2019-14234"] is settled


def test_the_organisation_score_is_absent_even_when_a_council_ran():
    settled = CouncilAssessment(advisory_id="CVE-1", vector=TOTAL_LOSS, single_assessor=True)
    named = [absence.what for absence in a_report(council=(settled,)).not_assessed]
    assert "Organisation Risk Score" in named


def test_the_same_run_builds_the_same_record():
    assert a_report(components=(DJANGO,), findings=(finding(DJANGO),)) == a_report(
        components=(DJANGO,), findings=(finding(DJANGO),)
    )


@pytest.mark.parametrize(("what", "because"), [("", "a reason"), ("a thing", "")])
def test_an_absence_that_does_not_say_what_or_why_is_refused(what, because):
    with pytest.raises(ValueError, match="must say what is missing and why"):
        Absence(what, because)


@pytest.mark.parametrize("built", ["", "   "], ids=["empty", "blank"])
def test_a_database_naming_no_build_date_is_refused(built):
    with pytest.raises(ValueError, match="must give the date it was built"):
        AdvisoryDatabase(built)


def test_a_missing_database_date_must_say_why():
    with pytest.raises(ValueError, match="must say why it is missing"):
        UnknownAdvisoryDatabase("")


def test_an_unreadable_database_is_not_the_same_as_a_fresh_one():
    unknown = UnknownAdvisoryDatabase("no metadata.json on this machine")
    assert not isinstance(unknown, AdvisoryDatabase)
    assert not hasattr(unknown, "built_at")


@pytest.mark.parametrize("field", ["repository", "syft_version", "trivy_version"])
def test_provenance_a_reader_could_not_reproduce_the_run_from_is_refused(field):
    fields = {"repository": "r", "syft_version": "s", "trivy_version": "t", "database": DATABASE}
    with pytest.raises(ValueError, match=f"needs {field}"):
        RunProvenance(**{**fields, field: ""})


@pytest.mark.parametrize("given", [None, "2026-09-22", 0], ids=["none", "str", "int"])
def test_provenance_without_a_real_database_is_refused(given):
    with pytest.raises(TypeError, match="needs a database"):
        RunProvenance("r", "s", "t", given)


def test_an_artifact_nothing_could_join_to_is_carried_rather_than_dropped():
    # The third kind of nothing. The scanner used to refuse the whole run over
    # one of these; dropping it silently would have been the other wrong answer.
    report = a_report(components=(DJANGO,), unidentified=(unidentified(),))
    assert [one.name for one in report.unidentified_artifacts] == ["./local-action"]


def test_an_unidentifiable_artifact_is_not_counted_as_a_component():
    report = a_report(components=(DJANGO,), unidentified=(unidentified(),))
    assert report.component_count == 1
    assert report.components_without_findings == (DJANGO.purl,)


def test_a_run_nobody_answered_for_names_the_organisation_score_absent():
    named = {one.what: one.because for one in a_report().not_assessed}
    assert "no organisation answers were supplied" in named["Organisation Risk Score"]


def test_a_run_that_was_answered_for_does_not_claim_the_score_is_missing():
    one = finding(DJANGO)
    weighed = assess(one, all_answers({"EXP-1": Answer.YES}), per_source(one))
    report = a_report(findings=(finding(DJANGO),), risk=(weighed,))
    assert "Organisation Risk Score" not in [one.what for one in report.not_assessed]
    assert report.risk[weighed.advisory_id] is weighed


def test_an_unapproved_run_names_the_approval_absent_with_its_own_reason():
    report = a_report(approval=NotApproved("nobody looked"))
    named = {one.what: one.because for one in report.not_assessed}
    assert named["Approval record"] == "nobody looked"


def test_an_approved_run_does_not_claim_nobody_approved_it():
    signed = Approval("someone", Decision.APPROVED, "2026-09-23T09:14:00Z")
    report = a_report(approval=signed)
    assert "Approval record" not in [one.what for one in report.not_assessed]
    assert report.approval is signed


def test_an_override_naming_an_advisory_this_scan_found_matched_something():
    one = finding(DJANGO)
    report = a_report(findings=(one,), overridden=(one.advisory.advisory_id,))
    assert report.overrides_without_findings == ()


def test_an_override_naming_an_advisory_nothing_found_is_counted_not_dropped():
    # A mistyped advisory id used to apply to nothing quietly, and a deliberate
    # escalation that did not apply moved a finding a band with nothing said.
    report = a_report(findings=(finding(DJANGO),), overridden=("CVE-2021-42799",))
    assert report.overrides_without_findings == ("CVE-2021-42799",)


def test_an_override_that_matched_nothing_does_not_stop_the_run():
    # An answer file reused across repositories will legitimately name advisories
    # absent from one of them, so this is counted rather than refused.
    report = a_report(findings=(finding(DJANGO),), overridden=("CVE-OTHER",))
    assert len(report.findings) == 1


def test_overrides_that_matched_nothing_are_sorted_so_two_runs_agree():
    report = a_report(overridden=("CVE-2", "CVE-1"))
    assert report.overrides_without_findings == ("CVE-1", "CVE-2")
