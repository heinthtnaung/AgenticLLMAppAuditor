"""Guards on the record: what a run gathered, and what it is honest about not having."""

import pytest

from organisation.approval import Approval, Decision, NotApproved
from organisation.risk import assess, per_source
from council_runs import ALONE, council_ran, passed_over_entirely
from full_runs import fully_assessed
from report.record import (
    NO_COUNCIL_RUN,
    NOTHING_ABSENT,
    NOTHING_WAS_PUT_TO_IT,
    Absence,
    Report,
    build_report,
)
from scoring.library import APPROVED_QUESTIONS
from scoring.question import Answer
from report_samples import PROVENANCE, advisory, catalogue, component, finding, unidentified


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
    assert absences["Council ruling"] == NO_COUNCIL_RUN


def test_a_council_put_to_no_finding_is_an_absence_and_says_which_kind():
    # Scoped to nothing is not "no council ran": members were named, every
    # finding was passed over, and a reader given neither a ruling nor a reason
    # would read the silence as a nil result.
    passed = a_report(council=passed_over_entirely())
    absences = {one.what: one.because for one in passed.not_assessed}
    assert absences["Council ruling"] == NOTHING_WAS_PUT_TO_IT


def test_a_run_with_a_council_does_not_claim_it_had_none():
    settled = council_ran()
    report = a_report(council=(settled,))
    assert "Council ruling" not in [absence.what for absence in report.not_assessed]
    assert report.council["CVE-2019-14234"] is settled


def test_the_organisation_score_is_absent_even_when_a_council_ran():
    settled = council_ran(models=ALONE)
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


def test_an_artifact_nothing_could_join_to_is_carried_rather_than_dropped():
    # The third kind of nothing. Refusing the whole run over one of these turns a
    # non-issue into total failure, and dropping it silently is the other wrong answer.
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
    # Uncounted, a mistyped advisory id would apply to nothing quietly, and an
    # escalation that did not apply would leave a finding a band lower than intended.
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


def test_a_run_with_answers_an_approval_and_a_council_has_nothing_absent():
    assert fully_assessed().not_assessed == ()


def test_the_sentence_for_nothing_absent_names_every_absence_a_bare_run_carries():
    # A new kind of absence a bare run carries turns this red until the sentence names it.
    every = a_report().not_assessed
    unnamed = [one.what for one in every if one.what.lower() not in NOTHING_ABSENT.lower()]
    assert every and unnamed == []
