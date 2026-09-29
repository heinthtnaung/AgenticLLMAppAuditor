"""Guards on an escalated metric on the web page: where it went, what came back, and from whom.

Every ruling here comes out of the real council, chairman and escalation,
through `escalation_runs`. Which metrics a reader is shown is
`report.html_council`; this is what an escalated one looks like opened.
"""

from escalation_runs import ANOTHER_VALUE, SETTLING, by_metric, escalated, split_on_av
from report.html_council import council_entry
from report.html_metric import metric_details


def test_the_summary_says_what_the_council_left_it_as_and_what_escalation_made_of_it():
    opened = metric_details(by_metric(escalated(SETTLING))["AC"])
    assert "contested → escalated to big:27b: L (verified)" in opened


def test_a_value_outside_the_contest_is_summarised_as_no_settlement_with_why():
    opened = metric_details(by_metric(split_on_av(ANOTHER_VALUE))["AV"])
    assert "no settlement, L is not one of the contested values" in opened


def test_the_escalation_model_s_reply_follows_the_members_with_its_quotation():
    opened = metric_details(by_metric(escalated(SETTLING))["AC"])
    members = opened.index('class="members"')
    escalation = opened.index('class="members escalation"')
    assert members < escalation
    assert "big:27b (big), escalation model" in opened[escalation:]
    assert "requires a specially crafted payload" in opened[escalation:]


def test_a_metric_the_council_settled_carries_no_escalation_row():
    # AC: the verified quotation overruled the dissent, so nothing escalated it.
    settled_by_the_council = metric_details(by_metric(split_on_av({}))["AC"])
    assert "escalation" not in settled_by_the_council


def test_an_escalated_metric_is_opened_rather_than_counted_with_the_settled_rest():
    entry = council_entry(escalated(SETTLING))
    assert entry.count("<details") == 2
    assert "6 metrics settled" in entry
