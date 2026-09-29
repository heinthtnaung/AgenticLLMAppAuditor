"""Guards on why the sources differ on the web page: labelled as the model's, beside the sources."""

from explanation_runs import QUOTED, WHY, explained_report
from full_runs import fully_assessed
from report.explanation_words import MODEL_WRITTEN
from report.html_explanation import explanation_section
from report.html_layout import text
from report.html_report import as_html
from report.html_risk import risk_section


def test_a_disputed_finding_is_a_card_naming_the_model_and_what_it_left_out():
    page = explanation_section(explained_report())
    assert "<h2>Why the sources differ (2)</h2>" in page
    assert "explained by big:27b" in page and "1 item not kept" in page


def test_the_model_s_words_are_marked_as_its_own_and_the_quotation_shown_whole():
    page = explanation_section(explained_report())
    assert f'<span class="model-written">{MODEL_WRITTEN}</span>: {text(WHY)}' in page
    assert f'<blockquote class="evidence">{QUOTED}</blockquote>' in page


def test_a_finding_the_model_could_not_explain_says_why_and_one_that_agrees_is_absent():
    page = explanation_section(explained_report())
    assert "not explained: big:27b: the model offered 1 item" in page
    assert "CVE-AGREED" not in page


def test_the_section_follows_the_sources_and_is_never_in_the_risk_figures():
    page = as_html(fully_assessed())
    assert page.index("Sources disagree (") < page.index("Why the sources differ (")
    assert "It does not say what can be read" not in risk_section(fully_assessed())


def test_an_item_not_kept_never_reads_as_an_explanation():
    page = explanation_section(explained_report())
    assert "A second go." not in page and "all of the files" not in page
    assert "It is bad." not in page and "the whole disk" not in page
