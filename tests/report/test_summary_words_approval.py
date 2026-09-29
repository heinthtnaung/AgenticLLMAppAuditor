"""Guards on the summary's approval count: the rule it counted by, and whether anyone approved.

Both pages carry the one sentence, so a test of the wording is also a test that
each puts it in the summary.
"""

import html

from approval_runs import APPROVED, EXPOSED, QUIET, UNEXPOSED, approval_report
from report.html_report import as_html
from report.record import build_report
from report.summary_words import UNAPPROVED, UNWEIGHED, approval_count
from report.text_report import as_text
from report_samples import PROVENANCE, catalogue

WEIGHED_COUNT = (
    "Approval is needed for 2 of 3: a High or Critical Organisation Risk Score, "
    "or sources that disagree."
)


def test_a_weighed_record_counts_by_both_halves_of_the_rule():
    assert approval_count(approval_report(EXPOSED, APPROVED)) == WEIGHED_COUNT


def test_a_record_with_no_answers_says_only_disagreement_could_mark_a_finding():
    # Without it, "1 of 3" would read as both halves checked and one met.
    said = approval_count(approval_report(approval=APPROVED))
    assert said == f"Approval is needed for 1 of 3: sources that disagree. {UNWEIGHED}"
    assert "a High or Critical Organisation Risk Score" in UNWEIGHED


def test_findings_needing_approval_with_none_recorded_are_said_plainly():
    assert approval_count(approval_report(EXPOSED)) == f"{WEIGHED_COUNT} {UNAPPROVED}"


def test_nothing_needing_approval_is_not_told_that_nobody_approved_it():
    said = approval_count(approval_report(UNEXPOSED, findings=(QUIET,)))
    assert said.startswith("Approval is needed for 0 of 1")
    assert UNAPPROVED not in said


def test_a_record_with_no_finding_counts_nothing_for_approval():
    assert approval_count(build_report(PROVENANCE, catalogue(), (), {})) == ""


def test_both_pages_carry_the_count_in_their_summary():
    report = approval_report(EXPOSED)
    summary = " ".join(as_text(report).split("\n\n")[1].split("\n"))
    assert approval_count(report) in summary
    said = html.escape(approval_count(report), quote=True)
    assert f'<p class="count">{said}</p>' in as_html(report)
