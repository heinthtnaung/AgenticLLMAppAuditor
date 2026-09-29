"""Guards on one metric on the terminal page: what escalation made of it, and who said what."""

from escalation_runs import (
    ANOTHER_VALUE,
    SETTLING,
    TIMED_OUT,
    UNSTABLE_AND_INVENTED,
    by_metric,
    escalated,
    split_on_av,
)
from report.text_council import advisory_lines
from report.text_metric import ruling_lines


def headline(ruling) -> str:
    """Give the line a metric is headed by, without its indent."""
    return ruling_lines(ruling)[0].strip()


def test_a_contested_metric_the_escalation_settled_says_where_it_went_and_what_came_back():
    assert headline(by_metric(escalated(SETTLING))["AC"]) == (
        "AC  ·  contested → escalated to big:27b: L (verified)  ·  2 members"
    )


def test_an_unresolved_metric_the_escalation_settled_says_so_too():
    assert headline(by_metric(escalated(SETTLING))["S"]) == (
        "S  ·  unresolved → escalated to big:27b: U (verified)  ·  2 members"
    )


def test_the_escalation_model_is_listed_below_the_members_with_its_quotation():
    lines = [one.strip() for one in ruling_lines(by_metric(escalated(SETTLING))["AC"])]
    named = [one for one in lines if one.startswith("big:27b")]
    assert named == [
        "big:27b (big), escalation model  L  ·  high confidence  ·  quotation found in the advisory"
    ]
    assert lines[-1] == "“requires a specially crafted payload”"


def test_the_chairman_says_the_escalation_settled_it():
    lines = ruling_lines(by_metric(escalated(SETTLING))["AC"])
    assert lines[1].strip() == (
        "chairman: L  ·  the council left it open, and the escalation model's verified "
        "quotation settled it  ·  high confidence"
    )


def test_a_value_outside_the_contest_is_no_settlement_and_says_why():
    assert headline(by_metric(split_on_av(ANOTHER_VALUE))["AV"]) == (
        "AV  ·  contested → escalated to big:27b: no settlement, "
        "L is not one of the contested values  ·  2 members"
    )


def test_an_order_sensitive_or_unverified_reply_is_no_settlement_and_says_why():
    rulings = by_metric(escalated(UNSTABLE_AND_INVENTED))
    assert headline(rulings["AC"]).endswith(
        "no settlement, order-sensitive: L with the options in order, H reversed  ·  2 members"
    )
    assert headline(rulings["S"]).endswith(
        "no settlement, U, quotation not found in the advisory  ·  2 members"
    )


def test_a_decline_or_a_timeout_is_no_settlement_and_says_which():
    declined = by_metric(escalated({}))["S"]
    timed_out = by_metric(escalated({"AC": TIMED_OUT, "S": TIMED_OUT}))["S"]
    assert headline(declined).endswith("no settlement, declined  ·  2 members")
    assert headline(timed_out).endswith(
        "no settlement, failed: timed out after 180 s  ·  2 members"
    )


def test_an_escalated_metric_is_shown_rather_than_counted_with_the_settled_rest():
    lines = [one.strip() for one in advisory_lines(escalated(SETTLING))]
    assert "6 metrics settled" in lines
    assert sum("→ escalated to" in one for one in lines) == 2
