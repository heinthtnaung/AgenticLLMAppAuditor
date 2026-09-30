"""Guards on the Overview tab's panel: no source a column, and every filter count off a predicate.

The table gives no source a column of its own, and its filter segments count by the
same predicate the record uses -- `sources_agree` excludes a refused or unscored
finding, so neither is counted "agree". The two scales are named before the table,
and the longer phone data-labels do not grow the desktop column heads.
"""

from overview_runs import EXPOSED, agreeing, disagreeing, refused, report_of, unscored
from report.disagreement import sources_agree, sources_disagree
from report.html_overview import overview_panel, segments
from report.html_overview_rows import CVSS_PHONE_LABEL, RISK_PHONE_LABEL


def test_the_table_heads_six_columns_and_gives_no_source_a_column():
    page = overview_panel(report_of(disagreeing()))
    for column in ("Advisory", "Sources", "CVSS", "Org risk", "Council", "Approval"):
        assert f"<th>{column}</th>" in page
    assert "<th>ghsa" not in page and "<th>redhat" not in page


def test_each_segments_count_matches_the_records_own_predicate():
    # The bug the judge caught: refused and unscored findings counted as "agree".
    report = report_of(disagreeing(), agreeing(), refused(), unscored())
    counts = {one.tag: one.count for one in segments(report)}
    findings = report.findings
    assert counts["all"] == len(findings)
    assert counts["disagree"] == len([one for one in findings if sources_disagree(one)])
    assert counts["agree"] == len([one for one in findings if sources_agree(one)])
    assert counts["agree"] == 1


def test_the_longer_phone_labels_do_not_change_the_desktop_headers():
    # The desktop column heads stay short; only the stacked data-labels grow.
    page = overview_panel(report_of(disagreeing()))
    assert "<th>CVSS</th>" in page and "<th>Org risk</th>" in page
    assert f"<th>{CVSS_PHONE_LABEL}</th>" not in page
    assert f"<th>{RISK_PHONE_LABEL}</th>" not in page


def test_the_filter_offers_all_the_tabs_promised():
    page = overview_panel(report_of(disagreeing(), answers=EXPOSED))
    for tag in ("all", "approval", "disagree", "agree", "settled"):
        assert f'data-filter="{tag}"' in page


def test_the_two_scales_are_named_before_the_table():
    page = overview_panel(report_of(disagreeing()))
    assert "Two scores, never merged" in page
    assert page.index("Two scores, never merged") < page.index("All findings")


def test_the_summary_counts_lead_the_findings_table():
    page = overview_panel(report_of(disagreeing()))
    assert '<p class="count">' in page
    assert "1 finding across 2 components" in page
