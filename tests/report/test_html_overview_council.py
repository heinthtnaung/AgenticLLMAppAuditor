"""Guards on the overview's Council cell: the settled vector and band, or the metrics left open.

The band and the open metrics are read off the record's council outcome, never
worked out in the page.
"""

from council_runs import DISSENTING, council_ran
from report.council_record import CouncilNotAsked
from report.html_overview_council import council_cell, open_metrics_line
from report.record import build_report
from report_samples import CONFIDENTIALITY_ONLY, PROVENANCE, catalogue, component, finding

DJANGO = component()


def report_with(*council):
    """Build a report whose council carries these outcomes."""
    raised = tuple(
        finding(DJANGO, advisory_id=one.advisory_id, vectors={"ghsa": CONFIDENTIALITY_ONLY})
        for one in council
    )
    return build_report(PROVENANCE, catalogue(DJANGO), raised, {}, council)


def test_a_settled_vector_shows_its_score_and_band_on_a_cvss_chip():
    report = report_with(council_ran("CVE-2019-14234"))
    cell = council_cell(report, "CVE-2019-14234")
    assert 'href="#council/CVE-2019-14234"' in cell
    assert '<span class="badge badge-ok">Settled</span>' in cell
    assert '<span class="src">council</span>' in cell
    assert '<span class="value">9.8</span><span class="band">Critical</span>' in cell


def test_no_settled_vector_lists_the_metrics_the_council_left_open():
    report = report_with(council_ran("CVE-2019-14234", **DISSENTING))
    cell = council_cell(report, "CVE-2019-14234")
    assert '<span class="badge badge-muted">No vector</span>' in cell
    assert "open: AV" in cell


def test_a_finding_the_council_was_not_put_to_says_so():
    report = build_report(
        PROVENANCE, catalogue(DJANGO), (finding(DJANGO),), {},
        (CouncilNotAsked("CVE-2019-14234", "the sources already settled it"),),
    )
    cell = council_cell(report, "CVE-2019-14234")
    assert '<span class="badge badge-muted">not asked</span>' in cell


def test_a_finding_with_no_council_outcome_shows_a_dash():
    report = build_report(PROVENANCE, catalogue(DJANGO), (finding(DJANGO),), {})
    assert council_cell(report, "CVE-2019-14234") == '<td data-label="Council">—</td>'


def test_the_open_metrics_come_off_the_record():
    outcome = council_ran("CVE-2019-14234", **DISSENTING)
    assert "AV" in open_metrics_line(outcome)
