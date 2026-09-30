"""Guards on the same-evidence flag on the web page: in the markup, and fetching nothing."""

from report.council_words import SAME_EVIDENCE
from report.html_layout import SEPARATOR
from report.html_report import as_html
from report_pages import parsed
from same_evidence_runs import report_of, same_words, unflagged

FLAG = f'<span class="flag">{SAME_EVIDENCE}</span>'


def test_the_flag_is_in_the_page_itself_so_it_reads_with_scripts_off():
    page = as_html(report_of(same_words()))
    summary_at = page.index(FLAG)
    assert page.rfind("<summary>", 0, summary_at) > page.rfind("</summary>", 0, summary_at)


def test_the_flag_adds_no_script_and_reaches_nowhere_off_the_page():
    page = parsed(as_html(report_of(same_words())))
    assert (page.scripts, page.with_src, page.offsite) == (1, [], [])


def test_the_page_changes_only_by_the_flag_and_the_dot_before_it():
    flagged = as_html(report_of(same_words()))
    plain = as_html(report_of(unflagged(same_words())))
    assert flagged.replace(f"{SEPARATOR}{FLAG}", "", 1) == plain
