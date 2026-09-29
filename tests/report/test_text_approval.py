"""Guards on the terminal's list of findings that need approval, each with its reasons."""

from approval_runs import APPROVED, EXPOSED, QUIET, SEVERE, UNEXPOSED, approval_report
from report.text_approval import approval_needed_block
from report.text_report import as_text

BOTH = "a High or Critical Organisation Risk Score  ·  sources that disagree"


def test_every_finding_needing_approval_is_listed_with_the_halves_it_meets():
    assert approval_needed_block(approval_report(EXPOSED)).split("\n") == [
        "NEEDS APPROVAL (2)",
        f"  CVE-2019-14234  {BOTH}",
        "  CVE-2020-14343  a High or Critical Organisation Risk Score",
    ]


def test_a_record_needing_no_approval_prints_no_block():
    assert approval_needed_block(approval_report(UNEXPOSED, findings=(SEVERE, QUIET))) == ""


def test_the_list_comes_just_before_the_approval_it_is_for():
    page = as_text(approval_report(EXPOSED, APPROVED))
    assert page.index("NEEDS APPROVAL (2)") < page.index("APPROVAL\n") < page.index("NOT ASSESSED")
