"""Guards on the Overview tab's findings table: no source a column, and every count off a predicate.

The table lists what each finding carries: the CVSS and Org risk cells hold one
mini chip per source, so a real repository where NVD is on 4 rows of 18 is
rendered honestly. Each filter segment's count and each row's group tag are held
to the record's own predicate -- `sources_agree` excludes a refused or unscored
finding, so neither is counted or tagged "agree".
"""

from organisation.risk import assess, per_source
from report.disagreement import agreement_unchecked, sources_agree, sources_disagree
from report.html_overview import (
    CVSS_PHONE_LABEL, RISK_PHONE_LABEL, finding_row, overview_panel, segments,
)
from report.record import build_report
from report_samples import (
    CONFIDENTIALITY_ONLY, LOW_CONFIDENTIALITY, PROVENANCE, TOTAL_LOSS, VERSION_2_VECTOR,
    catalogue, component, finding,
)
from scoring.library import APPROVED_QUESTIONS
from scoring.question import Answer

DJANGO = component()
PYYAML = component("pyyaml", "5.1")


def all_answers(overrides=None) -> dict:
    """Answer every approved question No, except the ones a test names."""
    return {**{asked.question_id: Answer.NO for asked in APPROVED_QUESTIONS}, **(overrides or {})}


EXPOSED = all_answers({"EXP-1": Answer.YES, "BUS-1": Answer.YES, "BUS-2": Answer.YES})


def disagreeing():
    """One finding two sources read differently."""
    return finding(DJANGO, vectors={"ghsa": LOW_CONFIDENTIALITY, "redhat": TOTAL_LOSS})


def agreeing():
    """One finding whose one readable source stands alone, so its sources agree."""
    return finding(PYYAML, advisory_id="CVE-AGREE", vectors={"ghsa": CONFIDENTIALITY_ONLY})


def refused():
    """One finding whose readable source stands beside a vector this calculator refused."""
    return finding(DJANGO, advisory_id="CVE-REFUSED",
                   vectors={"ghsa": CONFIDENTIALITY_ONLY, "nvd": VERSION_2_VECTOR})


def unscored():
    """One finding nobody published a readable vector for."""
    return finding(DJANGO, advisory_id="CVE-UNSCORED", vectors={"nvd": VERSION_2_VECTOR})


def report_of(*findings, council=(), answers=None):
    """Build a report over these findings, weighed and settled where a test asks."""
    risk = [assess(one, answers, per_source(one)) for one in findings] if answers else ()
    return build_report(PROVENANCE, catalogue(DJANGO, PYYAML), findings, {}, council, risk)


def test_the_table_heads_six_columns_and_gives_no_source_a_column():
    page = overview_panel(report_of(disagreeing()))
    for column in ("Advisory", "Sources", "CVSS", "Org risk", "Council", "Approval"):
        assert f"<th>{column}</th>" in page
    assert "<th>ghsa" not in page and "<th>redhat" not in page


def test_a_row_carries_one_mini_chip_per_source_the_finding_has():
    row = finding_row(report_of(disagreeing()), disagreeing())
    assert '<span class="src">ghsa</span>' in row
    assert '<span class="src">redhat</span>' in row
    assert row.count("mini cvss") == 2


def test_each_segments_count_matches_the_records_own_predicate():
    # The bug the judge caught: refused and unscored findings counted as "agree".
    report = report_of(disagreeing(), agreeing(), refused(), unscored())
    counts = {one.tag: one.count for one in segments(report)}
    findings = report.findings
    assert counts["all"] == len(findings)
    assert counts["disagree"] == len([one for one in findings if sources_disagree(one)])
    assert counts["agree"] == len([one for one in findings if sources_agree(one)])
    assert counts["agree"] == 1


def test_a_row_is_tagged_by_the_group_predicate_it_meets():
    report = report_of(disagreeing(), agreeing(), refused(), unscored())
    rows = {one.advisory.advisory_id: finding_row(report, one) for one in report.findings}
    tag_of = {advisory: group_of(row) for advisory, row in rows.items()}
    assert tag_of["CVE-2019-14234"] == "disagree"
    assert tag_of["CVE-AGREE"] == "agree"
    assert tag_of["CVE-REFUSED"] == "refused"
    assert tag_of["CVE-UNSCORED"] == "unscored"


def group_of(row: str) -> str:
    """Read the group tag off a rendered row, the first of its data-tags."""
    tags = row.split('data-tags="', 1)[1].split('"', 1)[0]
    return tags.split(" ")[0]


def test_a_refused_finding_is_neither_agree_nor_disagree_in_the_record():
    # The tag and the record agree: a refused finding is agreement nobody checked.
    assert agreement_unchecked(refused())
    assert not sources_agree(refused()) and not sources_disagree(refused())


def test_the_marks_ride_on_the_row_beside_the_group():
    one = disagreeing()
    row = finding_row(report_of(one, council=(_settled(),), answers=EXPOSED), one)
    assert 'data-tags="disagree approval settled"' in row


def _settled():
    """A council outcome that settled a vector for the disagreeing finding."""
    from council_runs import council_ran
    return council_ran("CVE-2019-14234")


def test_the_org_risk_cell_shows_a_mini_per_source_linked_to_the_risk_entry():
    one = disagreeing()
    row = finding_row(report_of(one, answers=EXPOSED), one)
    assert 'href="#risk/CVE-2019-14234"' in row
    assert row.count("mini risk") == 2


def test_a_finding_nobody_answered_for_shows_a_dash_in_the_org_risk_cell():
    row = finding_row(report_of(disagreeing()), disagreeing())
    assert f'<td data-label="{RISK_PHONE_LABEL}"><div class="minis">—</div></td>' in row


def test_the_stacked_phone_labels_say_the_cell_holds_a_score_per_source():
    # At phone width the row stacks and each cell shows its data-label. The
    # template's CVSS and Org risk cells read longer there than the column head.
    row = finding_row(report_of(disagreeing(), answers=EXPOSED), disagreeing())
    assert f'data-label="{CVSS_PHONE_LABEL}"' in row
    assert f'data-label="{RISK_PHONE_LABEL}"' in row
    assert (CVSS_PHONE_LABEL, RISK_PHONE_LABEL) == ("CVSS by source", "Org risk by source")


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
