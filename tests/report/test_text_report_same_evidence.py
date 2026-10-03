"""Guards on the same-evidence flag on the terminal page: one line more, and nothing else."""

from report.council_words import SAME_EVIDENCE
from report.text_report import as_text
from same_evidence_runs import report_of, same_words, unflagged


def test_the_page_gains_the_flag_line_and_every_other_line_is_unchanged():
    flagged = as_text(report_of(same_words())).splitlines()
    plain = as_text(report_of(unflagged(same_words()))).splitlines()
    assert [one for one in flagged if one.strip() != SAME_EVIDENCE] == plain
    assert len(flagged) == len(plain) + 1
