"""Guards on the explanation kept: items quoting the advisory, on a disputed metric, once each."""

import json

import pytest

from council.explanation import (
    EMPTY_WHY,
    NOT_A_DISPUTED_METRIC,
    REPEAT,
    UNVERIFIED_QUOTATION,
    Explained,
    NotExplained,
    explain,
)
from council.explanation_prompt import EXPLANATION_PROMPT_VERSION, ExplanationPrompt
from council.transport import ModelUnavailable
from council_samples import NOT_IN_THE_ADVISORY, QUOTABLE, RAW_ADVISORY, member

DISAGREEMENT = {"AV": {"nvd": "N", "ghsa": "L"}, "A": {"nvd": "H", "ghsa": "N"}}
EXPLAINER = member("big-local", model="big:27b", family="big")


def item(metric: str = "AV", quotation: str = QUOTABLE, why: str = "It says remote.") -> dict:
    """Give one item as the explainer would write it."""
    return {"metric": metric, "why": why, "quotation": quotation}


def explained(*items, reply: str = "") -> NotExplained | Explained:
    """Ask the explainer about the sample disagreement, answering with these items."""
    asked = []

    def said(who, prompt):
        """Answer the explainer's question, noting what it was asked."""
        asked.append(prompt)
        return reply or json.dumps({"items": list(items)})

    outcome = explain(RAW_ADVISORY, DISAGREEMENT, EXPLAINER, {"ollama": said})
    assert [type(one) for one in asked] == [ExplanationPrompt]
    return outcome


def test_an_item_whose_quotation_is_in_the_advisory_is_kept_with_the_model_and_version():
    outcome = explained(item("AV"))
    assert isinstance(outcome, Explained)
    assert (outcome.model, outcome.prompt_version, outcome.dropped) == (
        "big:27b", EXPLANATION_PROMPT_VERSION, (),
    )
    assert [(one.metric, one.quotation) for one in outcome.items] == [("AV", QUOTABLE)]


@pytest.mark.parametrize(
    ("extra", "reason", "found"),
    [
        (item("A", quotation=NOT_IN_THE_ADVISORY), UNVERIFIED_QUOTATION, False),
        (item("C"), NOT_A_DISPUTED_METRIC, True),
        (item("AV", why="A second go."), REPEAT, True),
        (item("A", why=""), EMPTY_WHY, True),
    ],
    ids=["an invented quotation", "a metric the sources agree on", "a second item", "no why"],
)
def test_an_item_not_kept_is_recorded_whole_with_its_reason_and_the_rest_kept(
    extra, reason, found
):
    outcome = explained(item("AV"), extra)
    assert [one.why for one in outcome.items] == ["It says remote."]
    (dropped,) = outcome.dropped
    assert (dropped.reason, dropped.quotation_found) == (reason, found)
    said = dropped.item
    assert (said.metric, said.why) == (extra["metric"], extra["why"])
    assert said.quotation == extra["quotation"]


def test_the_first_reason_that_applies_is_the_one_recorded():
    # An agreed metric and an empty why each outrank a bad quotation, and a bad
    # quotation outranks a repeat.
    outcome = explained(
        item("AV"), item("C", quotation=NOT_IN_THE_ADVISORY),
        item("AV", why="Again.", quotation=NOT_IN_THE_ADVISORY),
        item("A", why="", quotation=NOT_IN_THE_ADVISORY),
    )
    assert [one.reason for one in outcome.dropped] == [
        NOT_A_DISPUTED_METRIC, UNVERIFIED_QUOTATION, EMPTY_WHY,
    ]


def test_when_every_item_is_dropped_the_finding_is_not_explained_and_keeps_them_all():
    outcome = explained(item("AV", quotation=NOT_IN_THE_ADVISORY), item("C"))
    assert isinstance(outcome, NotExplained)
    assert outcome.because == (
        "the model offered 2 items, and none was kept "
        "(not a disputed metric 1, unverified quotation 1)"
    )
    assert [one.reason for one in outcome.dropped] == [UNVERIFIED_QUOTATION, NOT_A_DISPUTED_METRIC]


def test_a_reply_with_no_item_is_not_explained_and_says_so():
    assert explained().because == "the model offered no item"


def test_a_reply_holding_two_objects_is_not_explained_rather_than_read():
    twice = f"{json.dumps({'items': [item()]})} {json.dumps({'items': [item()]})}"
    outcome = explained(reply=twice)
    assert isinstance(outcome, NotExplained)
    assert "holds 2 JSON objects" in outcome.because


def test_a_call_that_fails_is_not_explained_and_keeps_the_server_s_account():
    def timing_out(who, prompt):
        """Fail as a slow server fails."""
        raise ModelUnavailable("did not answer within 180 s")

    outcome = explain(RAW_ADVISORY, DISAGREEMENT, EXPLAINER, {"ollama": timing_out})
    assert (type(outcome), outcome.because) == (
        NotExplained, "no readable explanation: did not answer within 180 s",
    )


def test_a_disagreement_that_is_not_one_is_refused_before_any_model_is_asked():
    with pytest.raises(ValueError, match="agree on AV"):
        explain(RAW_ADVISORY, {"AV": {"nvd": "N", "ghsa": "N"}}, EXPLAINER, {})
