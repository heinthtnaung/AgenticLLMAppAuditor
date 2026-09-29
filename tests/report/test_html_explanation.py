"""Guards on why the sources differ: embedded in the contested card, labelled as the model's.

The redesign moves the explanation onto the disagreement card that raises the
question, rather than a tab of its own. These hold that the model's prose is
marked as unchecked, the quotation is shown whole, a finding nobody explained
says why, and an agreeing finding carries no block.
"""

from explanation_runs import QUOTED, WHY, explained_report
from report.explanation_words import MODEL_WRITTEN
from report.html_explanation import why_block
from report.html_layout import text
from report.html_report import as_html


def findings_by_id(report) -> dict:
    """Index a report's findings by their advisory id, so a test can name one."""
    return {one.advisory.advisory_id: one for one in report.findings}


def block_for(advisory_id: str) -> str:
    """Give the why block for one finding of the explained report."""
    report = explained_report()
    return why_block(report, findings_by_id(report)[advisory_id])


def test_a_disputed_finding_gets_a_block_naming_the_model_and_what_it_left_out():
    block = block_for("CVE-EXPLAINED")
    assert "<h4>Why the sources differ</h4>" in block
    assert "explained by big:27b" in block and "1 item not kept" in block


def test_the_models_words_are_marked_as_its_own_and_the_quotation_shown_whole():
    block = block_for("CVE-EXPLAINED")
    assert f'<span class="tag tag-warn">{MODEL_WRITTEN}</span> {text(WHY)}' in block
    assert f'<blockquote class="evidence">{QUOTED}</blockquote>' in block
    assert "quotation found in the advisory" in block


def test_a_finding_the_model_could_not_explain_says_why():
    assert "not explained: big:27b: the model offered 1 item" in block_for("CVE-UNEXPLAINED")


def test_a_finding_whose_sources_agree_carries_no_why_block():
    # The block is asked for only on a contested card, so an agreeing finding's
    # card never carries one whatever the record holds about it.
    page = as_html(explained_report())
    card = page.split('id="agree-CVE-AGREED"')[1].split("</article>")[0]
    assert "Why the sources differ" not in card


def test_the_block_is_inside_the_contested_card_after_its_sources():
    page = as_html(explained_report())
    card = page.split('id="disagree-CVE-EXPLAINED"')[1].split("</article>")[0]
    assert card.index("data compact rt") < card.index("Why the sources differ")


def test_an_item_not_kept_never_reads_as_an_explanation():
    page = as_html(explained_report())
    assert "A second go." not in page and "all of the files" not in page
    assert "It is bad." not in page and "the whole disk" not in page
