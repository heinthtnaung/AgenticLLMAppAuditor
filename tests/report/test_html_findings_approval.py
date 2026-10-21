"""Guards on the approval mark on the page: on the head of every card that needs one."""

from approval_runs import APPROVED, DISPUTED, EXPOSED, OVERRIDDEN, approval_report
from report.html_finding_card import card_head
from report.html_findings import agreements_panel, disagreements_panel
from report.record import build_report
from report_samples import PROVENANCE, catalogue, component, finding

REASONS = "a High or Critical Organisation Risk Score and sources that disagree"
BOTH = f"needs approval: {REASONS}"
RISK_ONLY = "needs approval: a High or Critical Organisation Risk Score"


def test_a_contested_card_is_marked_with_both_halves_it_meets():
    page = disagreements_panel(approval_report(EXPOSED))
    assert f'<span class="badge badge-alarm">{BOTH}</span>' in page


def test_an_agreeing_card_is_marked_too_when_its_score_is_high():
    page = agreements_panel(approval_report(EXPOSED))
    assert page.count(f'<span class="badge badge-alarm">{RISK_ONLY}</span>') == 1
    assert page.count('class="card finding"') == 2


def test_a_contested_card_shows_the_decision_once_the_audit_is_approved():
    head = card_head(approval_report(EXPOSED, APPROVED), DISPUTED)
    assert f'<span class="badge badge-ok">approved: {REASONS}</span>' in head
    assert "needs approval" not in head


def test_a_contested_card_shows_a_distinct_overridden_badge_when_overridden():
    head = card_head(approval_report(EXPOSED, OVERRIDDEN), DISPUTED)
    assert f'<span class="badge badge-warn">overridden: {REASONS}</span>' in head


def test_a_finding_needing_no_approval_carries_no_mark():
    one = finding(component())
    report = build_report(PROVENANCE, catalogue(component()), (one,), {})
    assert "needs approval" not in card_head(report, one)
