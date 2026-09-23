"""Guards on the record: what a run gathered, and what it is honest about not having."""

import pytest

from report.record import (
    Absence,
    AdvisoryDatabase,
    CouncilAssessment,
    Report,
    RunProvenance,
    UnknownAdvisoryDatabase,
    build_report,
)
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

DJANGO = component()
PYYAML = component("pyyaml", "5.1")


def a_report(components=(), findings=(), advisories=None, council=(), unidentified=()):
    """Build one report from whatever a test is about."""
    found = catalogue(*components, unidentified=unidentified)
    return build_report(PROVENANCE, found, findings, advisories or {}, council)


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
