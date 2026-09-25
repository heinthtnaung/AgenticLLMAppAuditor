"""Guards on what a record says it does not carry, and on each reason it gives."""

import pytest

from council_runs import ALONE, council_ran, passed_over_entirely
from full_runs import fully_assessed
from organisation.approval import Approval, Decision, NotApproved
from organisation.risk import assess, per_source
from report.absences import (
    NO_COUNCIL_RUN,
    NOTHING_ABSENT,
    NOTHING_TO_PUT,
    NOTHING_TO_WEIGH,
    NOTHING_WAS_PUT_TO_IT,
    UNREAD_MANIFEST,
    Absence,
    Coverage,
)
from report.record import build_report
from report.text_report import as_text
from report_samples import PROVENANCE, catalogue, component, finding
from scoring.library import APPROVED_QUESTIONS
from scoring.question import Answer

UNREAD = ("frontend/package.json", "package.json")
WHAT_A_BARE_RUN_LEAVES_OUT = ["Organisation Risk Score", "Approval record", "Council ruling"]


def all_answers(overrides=None) -> dict:
    """Answer every approved question No, except the ones a test names."""
    return {**{asked.question_id: Answer.NO for asked in APPROVED_QUESTIONS}, **(overrides or {})}


DJANGO = component()


def a_report(
    components=(), findings=(), advisories=None, council=(), unidentified=(),
    risk=(), approval=None, overridden=(), coverage=Coverage(),
):
    """Build one report from whatever a test is about."""
    found = catalogue(*components, unidentified=unidentified)
    return build_report(
        PROVENANCE, found, findings, advisories or {}, council, risk, approval, overridden, coverage
    )


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


@pytest.mark.parametrize(("what", "because"), [("", "a reason"), ("a thing", "")])
def test_an_absence_that_does_not_say_what_or_why_is_refused(what, because):
    with pytest.raises(ValueError, match="must say what is missing and why"):
        Absence(what, because)


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


def test_a_run_with_answers_an_approval_and_a_council_has_nothing_absent():
    assert fully_assessed().not_assessed == ()


def test_the_sentence_for_nothing_absent_names_every_absence_a_bare_run_carries():
    # A new kind of absence a bare run carries turns this red until the sentence names it.
    every = a_report().not_assessed
    unnamed = [one.what for one in every if one.what.lower() not in NOTHING_ABSENT.lower()]
    assert every and unnamed == []


@pytest.mark.parametrize("asked, what, because", [
    (Coverage(answers_given=True), "Organisation Risk Score", NOTHING_TO_WEIGH),
    (Coverage(council_named=True), "Council ruling", NOTHING_TO_PUT),
])
def test_asking_for_something_with_no_finding_to_ask_about_names_that_cause(asked, what, because):
    absent = {one.what: one.because for one in a_report(coverage=asked).not_assessed}
    assert absent[what] == because


def test_each_manifest_nothing_was_read_from_is_named_first_with_why():
    unread = Coverage(unread_manifests=UNREAD)
    report = build_report(PROVENANCE, catalogue(), (), {}, coverage=unread)
    named = [(one.what, one.because) for one in report.not_assessed]
    assert named[:2] == [(path, UNREAD_MANIFEST) for path in UNREAD]
    assert [one for one, _ in named[2:]] == WHAT_A_BARE_RUN_LEAVES_OUT


def test_the_record_keeps_the_manifests_it_could_not_read():
    report = fully_assessed(Coverage(unread_manifests=UNREAD))
    assert report.coverage.unread_manifests == UNREAD


def test_a_run_that_assessed_everything_else_still_names_an_unread_manifest():
    # "Nothing" under the heading would be the one thing the section exists to prevent.
    report = fully_assessed(Coverage(unread_manifests=("package.json",)))
    assert [one.what for one in report.not_assessed] == ["package.json"]
    assert NOTHING_ABSENT not in as_text(report)
