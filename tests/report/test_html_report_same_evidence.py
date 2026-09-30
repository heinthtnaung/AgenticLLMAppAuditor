"""Guards on the same-evidence flag on the web page: in the markup, and fetching nothing."""

from report.council_words import SAME_EVIDENCE
from report.html_council_flag import SAME_EVIDENCE_LABEL
from report.html_layout import SEPARATOR
from report.html_report import as_html
from report_pages import parsed
from same_evidence_runs import report_of, same_words, unflagged

FLAG = f'<span class="flag">{SAME_EVIDENCE}</span>'
# The council tab spells the flag out in full; the overview cell names the metric compactly.
CELL_FLAG = f'<span class="flag">{SAME_EVIDENCE_LABEL}: AV</span>'


def test_the_flag_is_in_the_page_itself_so_it_reads_with_scripts_off():
    page = as_html(report_of(same_words()))
    summary_at = page.index(FLAG)
    assert page.rfind("<summary>", 0, summary_at) > page.rfind("</summary>", 0, summary_at)


def test_the_flag_adds_no_script_and_reaches_nowhere_off_the_page():
    page = parsed(as_html(report_of(same_words())))
    assert (page.scripts, page.with_src, page.offsite) == (1, [], [])


def test_the_page_changes_only_by_the_flags_it_adds():
    # The flag now names the metric on the overview cell as well as spelling it out
    # in full on the council tab; it stays display-only, so those are the whole
    # difference. This finding agrees, so no contested card carries it here.
    flagged = as_html(report_of(same_words()))
    plain = as_html(report_of(unflagged(same_words())))
    stripped = flagged.replace(f"{SEPARATOR}{FLAG}", "", 1).replace(CELL_FLAG, "", 1)
    assert stripped == plain
