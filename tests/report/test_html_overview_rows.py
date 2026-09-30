"""Guards on one finding's row: one mini chip per source, and the group tag it meets.

The CVSS and Org risk cells hold one mini chip per source the finding carries, so a
real repository where NVD is on 4 rows of 18 is rendered honestly. Each row's group
tag is held to the record's own predicate -- a refused finding is agreement nobody
checked, neither agree nor disagree -- and the approval and settled marks ride on
the row beside it.
"""

from overview_runs import EXPOSED, agreeing, disagreeing, refused, report_of, unscored
from report.disagreement import agreement_unchecked, sources_agree, sources_disagree
from report.html_overview_rows import CVSS_PHONE_LABEL, RISK_PHONE_LABEL, finding_row


def test_a_row_carries_one_mini_chip_per_source_the_finding_has():
    row = finding_row(report_of(disagreeing()), disagreeing())
    assert '<span class="src">ghsa</span>' in row
    assert '<span class="src">redhat</span>' in row
    assert row.count("mini cvss") == 2


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
