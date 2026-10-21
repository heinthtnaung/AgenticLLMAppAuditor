"""An approval attached after the run says so; one given during the run says nothing of it.

The default is the whole point: a decision read from the answers file during a run
leaves `attached_after_run` False, so an ordinary run's three reports are byte for
byte what they always were. Only `cli.approve` sets it, and then the line appears.
"""

from dataclasses import replace

from organisation.approval import Approval, Decision
from report.approval_needed import needing_approval
from report.approval_words import ATTACHED_AFTER_RUN
from report.html_approval import approval_status
from report.html_report import as_html
from report.json_report import as_json
from report.record import Report, build_report
from report.text_report import as_text
from report_samples import (
    CONFIDENTIALITY_ONLY,
    LOW_CONFIDENTIALITY,
    PROVENANCE,
    catalogue,
    component,
    finding,
)

DURING_RUN = Approval("hein", Decision.APPROVED, "2026-09-23T09:15:00Z", "reviewed")
# Two sources reading confidentiality apart, so the rule flags the finding and a badge shows.
DISAGREEING = {"ghsa": CONFIDENTIALITY_ONLY, "nvd": LOW_CONFIDENTIALITY}


def report_with(approval: Approval) -> Report:
    """Build a small approved report to render."""
    one = finding(component())
    return build_report(PROVENANCE, catalogue(component()), (one,), {}, approval=approval)


def test_an_approval_defaults_to_not_attached_after_the_run():
    # The default keeps an ordinary run byte-identical; a run never sets it.
    assert DURING_RUN.attached_after_run is False


def test_a_during_run_approval_renders_no_after_the_run_line():
    # The asserted gap: closing it (rendering the line unconditionally) turns this red.
    during = report_with(DURING_RUN)
    assert "attached_after_run" not in as_json(during)
    assert ATTACHED_AFTER_RUN not in as_text(during)
    assert ATTACHED_AFTER_RUN not in as_html(during)


def test_an_attached_after_run_approval_is_said_in_the_json():
    after = report_with(replace(DURING_RUN, attached_after_run=True))
    assert '"attached_after_run": true' in as_json(after)


def test_an_attached_after_run_approval_is_said_on_the_text_page():
    after = report_with(replace(DURING_RUN, attached_after_run=True))
    assert ATTACHED_AFTER_RUN in as_text(after)


def test_an_attached_after_run_approval_is_said_twice_on_the_html_page():
    # The masthead's glance and the overview card both carry it.
    after = report_with(replace(DURING_RUN, attached_after_run=True))
    assert as_html(after).count(ATTACHED_AFTER_RUN) == 2


def test_the_after_run_mark_renders_beside_the_per_finding_decision_badge():
    # A flagged finding shows the decision badge (approved/overridden); the after-run
    # mark sits on the same page, on the masthead and the overview card.
    one = finding(component(), vectors=DISAGREEING)
    overridden = replace(
        DURING_RUN, approver="dana", decision=Decision.OVERRIDDEN, attached_after_run=True
    )
    report = build_report(PROVENANCE, catalogue(component()), (one,), {}, approval=overridden)
    assert needing_approval(report)
    page = as_html(report)
    assert approval_status(report.approval)[0] in page.lower()
    assert ATTACHED_AFTER_RUN in page
