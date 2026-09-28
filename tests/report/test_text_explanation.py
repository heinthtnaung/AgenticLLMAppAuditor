"""Guards on why the sources differ on the terminal: labelled as the model's, beside the sources."""

from dataclasses import replace

from explanation_runs import QUOTED, WHY, explained_report
from full_runs import fully_assessed
from report.explanation_words import MODEL_WRITTEN
from report.text_explanation import explanation_block
from report.text_report import as_text
from report.text_risk import risk_block


def block_lines() -> list[str]:
    """Give the block's lines without their indent."""
    return [one.strip() for one in explanation_block(explained_report()).splitlines()]


def test_a_disputed_finding_is_listed_with_the_model_and_what_it_left_out():
    lines = block_lines()
    assert lines[0] == "WHY THE SOURCES DIFFER (2)"
    assert "CVE-EXPLAINED  explained by big:27b  ·  1 item not kept" in lines


def test_each_metric_shows_every_source_s_value_the_model_s_words_and_the_quotation():
    text = " ".join(block_lines())
    assert "C  ghsa H  ·  nvd L" in text
    assert f"{MODEL_WRITTEN}: {WHY}" in text
    assert f"“{QUOTED}”  ·  quotation found in the advisory" in text


def test_a_finding_the_model_could_not_explain_says_why():
    text = " ".join(block_lines())
    said = "CVE-UNEXPLAINED  not explained: big:27b: the model offered 1 item, and none quoted"
    assert said in text


def test_a_finding_whose_sources_agree_has_no_entry():
    assert "CVE-AGREED" not in explanation_block(explained_report())


def test_the_block_stands_beside_the_sources_and_never_in_the_risk_figures():
    page = as_text(fully_assessed())
    assert page.index("SOURCES DISAGREE") < page.index("WHY THE SOURCES DIFFER")
    assert "It does not say what can be read" not in risk_block(fully_assessed())


def test_a_run_that_asked_no_model_has_no_block():
    assert explanation_block(replace(explained_report(), explanations={})) == ""
