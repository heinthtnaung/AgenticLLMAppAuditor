"""Guards on the words for an escalation, which the terminal and the web page share."""

from dataclasses import replace

from council_runs import DISSENTING, council_ran
from escalation_runs import ANOTHER_VALUE, SETTLING, by_metric, escalated, split_on_av
from report.council_words import (
    NO_ESCALATION,
    escalated_who,
    escalation_named,
    outcome_said,
    why_unsettled,
)
from report.html_council import council_panel
from report.model_identity import OllamaVersion
from report.provenance import LocalModels
from report.record import build_report
from report.text_council import council_block
from report_samples import PROVENANCE, catalogue, component, finding


def test_a_metric_nothing_escalated_is_said_by_its_outcome_alone_as_before():
    rulings = by_metric(split_on_av({}))
    assert (outcome_said(rulings["AC"]), outcome_said(rulings["PR"])) == ("settled", "settled")


def test_an_escalated_metric_says_what_the_council_left_where_it_went_and_what_came_of_it():
    assert outcome_said(by_metric(escalated(SETTLING))["S"]) == (
        "unresolved → escalated to big:27b: U (verified)"
    )


def test_a_verified_reply_that_settled_nothing_is_a_value_outside_the_contest():
    escalation = by_metric(split_on_av(ANOTHER_VALUE))["AV"].escalation
    assert why_unsettled(escalation.said) == "L is not one of the contested values"


def test_the_escalation_model_is_named_apart_from_the_members():
    escalation = by_metric(escalated(SETTLING))["AC"].escalation
    assert escalated_who(escalation.said.member) == "big:27b (big), escalation model"


def asked_locally(escalation_model: str | None) -> LocalModels:
    """Give how a council run's local models were asked, naming this escalation model or none."""
    return LocalModels(
        server="http://127.0.0.1:11434", context_tokens=8192, timeout_seconds=180.0,
        temperature=0, seed=11, think=False, order_check=True, escalation_model=escalation_model,
        ollama_version=OllamaVersion("0.34.3"), models=(),
    )


def council_pages(escalation_model: str | None, outcome) -> tuple[str, str]:
    """Render one council record as the terminal and the web page show it."""
    provenance = replace(PROVENANCE, local_models=asked_locally(escalation_model))
    raised = (finding(component(), advisory_id=outcome.advisory_id),)
    report = build_report(provenance, catalogue(component()), raised, {}, (outcome,))
    return council_block(report), council_panel(report)


def test_a_run_naming_no_escalation_model_says_so_on_both_pages():
    assert escalation_named(asked_locally(None)) == [NO_ESCALATION]
    assert all(NO_ESCALATION in page for page in council_pages(None, council_ran(**DISSENTING)))


def test_a_run_naming_an_escalation_model_names_it_on_both_pages():
    said = "escalation model big:27b: asked each metric the council left open"
    assert escalation_named(asked_locally("big:27b")) == [said]
    assert all(said in page for page in council_pages("big:27b", escalated(SETTLING)))


def test_a_record_that_does_not_say_how_the_models_were_asked_says_nothing_of_escalation():
    assert escalation_named(None) == []
