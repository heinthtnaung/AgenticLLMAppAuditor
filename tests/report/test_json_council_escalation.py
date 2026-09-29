"""Guards on an escalation in the JSON record: what the council left, what the model said, whole."""

from escalation_runs import (
    SETTLING,
    TIMED_OUT,
    UNSTABLE_AND_INVENTED,
    by_metric,
    escalated,
)
from council.prompt import PROMPT_VERSION, REVERSED_PROMPT_VERSION
from report.json_council import ruling_of


def test_a_settled_escalation_carries_the_prior_outcome_and_the_model_s_whole_reply():
    metric = ruling_of(by_metric(escalated(SETTLING))["AC"])
    assert (metric["outcome"], metric["value"]) == ("settled", "L")
    assert metric["escalation"] == {
        "prior_outcome": "contested",
        "member": "big:27b",
        "provider": "ollama",
        "model": "big:27b",
        "family": "big",
        "ran_local": True,
        "prompt_version": PROMPT_VERSION,
        "reversed_prompt_version": REVERSED_PROMPT_VERSION,
        "said": "answered",
        "value": "L",
        "evidence": "requires a specially crafted payload",
        "confidence": "high",
        "evidence_verified": True,
        "reason": None,
        "orders": None,
    }


def test_an_escalation_that_settled_nothing_leaves_the_outcome_and_says_what_the_model_said():
    rulings = by_metric(escalated(UNSTABLE_AND_INVENTED))
    order_sensitive, invented = ruling_of(rulings["AC"]), ruling_of(rulings["S"])
    assert order_sensitive["outcome"] == "contested"
    assert order_sensitive["escalation"]["said"] == "order-sensitive"
    assert order_sensitive["escalation"]["orders"] == {"in_order": "L", "reversed": "H"}
    assert invented["outcome"] == "unresolved"
    assert (invented["escalation"]["value"], invented["escalation"]["evidence_verified"]) == (
        "U", False,
    )


def test_a_timed_out_escalation_is_recorded_as_failed_with_the_reason():
    metric = ruling_of(by_metric(escalated({"AC": TIMED_OUT, "S": TIMED_OUT}))["S"])
    assert (metric["escalation"]["said"], metric["escalation"]["reason"]) == (
        "failed", "timed out after 180 s",
    )


def test_a_metric_the_council_settled_carries_a_null_escalation():
    assert ruling_of(by_metric(escalated(SETTLING))["AV"])["escalation"] is None
