"""Guards on the approval mark on the page: on the heading of every card that needs one."""

from approval_runs import EXPOSED, approval_report
from report.html_findings import agreeing_section, contested_section, finding_name
from report_samples import component, finding

BOTH = "needs approval: a High or Critical Organisation Risk Score and sources that disagree"


def test_a_contested_card_is_marked_with_both_halves_it_meets():
    assert f'<span class="flag">{BOTH}</span>' in contested_section(approval_report(EXPOSED))


def test_an_agreeing_card_is_marked_too_when_its_score_is_high():
    page = agreeing_section(approval_report(EXPOSED))
    marked = '<span class="flag">needs approval: a High or Critical Organisation Risk Score</span>'
    assert page.count(marked) == 1
    assert page.count('<article class="finding">') == 2


def test_a_finding_needing_no_approval_carries_no_mark():
    assert "needs approval" not in finding_name(finding(component()))
