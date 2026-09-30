"""Guards on the same-evidence flag: it names the flagged metrics and decides nothing.

The flag is read off the council record's rulings, never worked out here, and it is
informational -- naming it on a cell or card adds the badge and nothing else, moving
no filter count, no row tag and no approval. The full sentence is the council tab's;
this is the compact page form.
"""

import re

from report.council_record import CouncilNotAsked
from report.html_council_flag import same_evidence_flag
from report.html_layout import SEPARATOR
from report.html_report import as_html
from report.record import build_report
from report_samples import (
    LOW_CONFIDENTIALITY,
    PROVENANCE,
    TOTAL_LOSS,
    catalogue,
    component,
    finding,
)
from same_evidence_runs import same_words, unflagged

DJANGO = component()
# The council tab joins its flag on with a separator; the cell and the card do not.
FLAG_SPAN = re.compile(rf"(?:{re.escape(SEPARATOR)})?" + r'<span class="flag">[^<]*</span>')


def report_with(one, outcome):
    """Build a report of one finding whose council carries this outcome."""
    return build_report(PROVENANCE, catalogue(DJANGO), (one,), {}, (outcome,))


def without_flags(page: str) -> str:
    """Strip every same-evidence flag the page carries, with any separator before it."""
    page = re.sub(r'<p class="card-flag">.*?</p>', "", page)
    return FLAG_SPAN.sub("", page)


def test_the_flag_names_every_metric_read_two_ways_from_the_same_words():
    assert same_evidence_flag(same_words()) == '<span class="flag">same evidence: AV</span>'


def test_a_ruling_read_apart_from_different_words_is_not_flagged():
    assert same_evidence_flag(unflagged(same_words())) == ""


def test_a_finding_the_council_was_not_asked_about_carries_no_flag():
    assert same_evidence_flag(CouncilNotAsked("CVE-1", "the sources agreed")) == ""


def test_a_finding_with_no_council_outcome_carries_no_flag():
    assert same_evidence_flag(None) == ""


def test_flagging_a_metric_adds_the_flag_and_changes_nothing_else_on_the_page():
    # The accepted limit stated as an assertion: the flag is display-only, so the
    # flagged page differs from the unflagged one by exactly the flag markup.
    one = finding(DJANGO, vectors={"ghsa": LOW_CONFIDENTIALITY, "redhat": TOTAL_LOSS})
    council = same_words(one.advisory.advisory_id)
    flagged, plain = report_with(one, council), report_with(one, unflagged(council))
    assert as_html(flagged) != as_html(plain)
    assert without_flags(as_html(flagged)) == as_html(plain)
