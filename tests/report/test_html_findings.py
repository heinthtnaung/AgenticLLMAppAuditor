"""Guards on a finding's shapes: every source a row, no source a column, a refused one kept.

On the repository under test NVD published a vector for 4 findings of 18, so a
layout with a column headed `nvd` is empty on 14 rows and looks right until a
real repository is on screen. What these hold is that the page renders the list
the finding carries -- one row per source under generic headers -- and that a
source nobody could read stays on the card, marked not scored, never a zero.
"""

import re

from explanation_runs import explained_report
from report.html_findings import NO_DISAGREEMENT, agreements_panel, disagreements_panel
from report.html_report import as_html
from report.record import build_report
from report_samples import (
    ADVISORY_URL,
    CONFIDENTIALITY_ONLY,
    ENVIRONMENTAL_VECTOR,
    LOW_CONFIDENTIALITY,
    PROVENANCE,
    REFUSED_DISSENT,
    TOTAL_LOSS,
    VERSION_2_VECTOR,
    catalogue,
    component,
    finding,
)
from same_evidence_runs import same_words

DJANGO = component()

# A score chip is the only place a figure goes, so its absence is the check that
# an unscored finding was not quietly given a number.
NO_CHIP = '<span class="value">'


def visible(page: str) -> str:
    """Give the text a reader sees, with tags stripped, so a split vector reads whole again."""
    return re.sub(r"<[^>]+>", "", page)


def report_of(*findings):
    """Build a report carrying these findings and nothing else."""
    return build_report(PROVENANCE, catalogue(DJANGO), findings, {})


def disagreeing():
    """One finding two sources read differently, 5.3 against 9.8."""
    return finding(DJANGO, vectors={"ghsa": LOW_CONFIDENTIALITY, "nvd": TOTAL_LOSS})


def test_a_run_with_no_contested_finding_names_the_absence_in_the_panel():
    agreed = finding(DJANGO, vectors={"ghsa": CONFIDENTIALITY_ONLY})
    page = disagreements_panel(report_of(agreed))
    assert NO_DISAGREEMENT in page
    assert "<article" not in page


def test_every_source_is_a_row_of_its_own_with_its_own_vector():
    page = disagreements_panel(report_of(disagreeing()))
    assert '<span class="source-name">ghsa</span>' in page
    assert '<span class="source-name">nvd</span>' in page
    # The vector is shown metric by metric; its visible text is what was published.
    seen = visible(page)
    assert LOW_CONFIDENTIALITY in seen and TOTAL_LOSS in seen


def test_each_score_is_written_beside_the_vector_it_derives_from():
    # The one rule the whole record is shaped by: a reader with the published
    # equations reproduces every number on the row beside it.
    seen = visible(disagreements_panel(report_of(disagreeing())))
    assert seen.index("5.3") < seen.index(LOW_CONFIDENTIALITY)
    assert seen.index("9.8") < seen.index(TOTAL_LOSS)


def test_a_contested_card_highlights_the_metrics_its_sources_read_apart():
    # LOW_CONFIDENTIALITY vs TOTAL_LOSS differ on C, I and A; the highlight and the
    # tooltip come from the vector and the record, never recomputed in the page.
    page = disagreements_panel(report_of(disagreeing()))
    assert '<span class="vm diff" title="Confidentiality: High">C:H</span>' in page
    assert '<span class="vm" title="Attack Vector: Network">AV:N</span>' in page


def test_a_contested_card_says_how_far_apart_and_which_bands_that_crosses():
    page = disagreements_panel(report_of(disagreeing()))
    assert "4.5 apart" in page
    assert "Critical and Medium" in page
    assert "Differ on" in page


def test_a_contested_card_flags_a_metric_the_council_read_two_ways_from_the_same_words():
    # Off the record's ruling, informational: the badge names the metric; the card's
    # spread, sources and approval are the disagreeing finding's own, untouched.
    one = disagreeing()
    council = (same_words(one.advisory.advisory_id),)
    report = build_report(PROVENANCE, catalogue(DJANGO), (one,), {}, council)
    page = disagreements_panel(report)
    assert '<p class="card-flag"><span class="flag">same evidence: AV</span></p>' in page


def test_an_agreeing_finding_gets_the_same_rows_without_a_spread():
    agreed = finding(DJANGO, vectors={"ghsa": CONFIDENTIALITY_ONLY, "nvd": CONFIDENTIALITY_ONLY})
    page = agreements_panel(report_of(agreed))
    assert '<span class="source-name">ghsa</span>' in page
    assert "apart" not in page


def test_a_finding_nobody_could_score_says_so_rather_than_showing_a_zero():
    # "Nobody scored this" and "somebody scored this 0.0" are different findings.
    nothing = finding(DJANGO, vectors={})
    page = agreements_panel(report_of(nothing))
    assert "No source published a readable v3 vector." in page
    assert NO_CHIP not in page


def test_a_refused_vector_is_kept_on_the_card_marked_not_scored():
    refused = finding(DJANGO, vectors={"nvd": VERSION_2_VECTOR})
    page = agreements_panel(report_of(refused))
    assert VERSION_2_VECTOR in page
    assert "not scored" in page
    assert NO_CHIP not in page


def test_a_refused_source_keeps_the_reason_the_calculator_would_not_read_it():
    refused = finding(DJANGO, vectors={"nvd": VERSION_2_VECTOR})
    assert '<span class="refusal">' in agreements_panel(report_of(refused))


def test_a_scored_finding_keeps_its_refused_source_too():
    both = finding(DJANGO, vectors={"ghsa": CONFIDENTIALITY_ONLY, "nvd": VERSION_2_VECTOR})
    page = agreements_panel(report_of(both))
    assert "not scored" in page
    assert '<span class="source-name">ghsa</span>' in page
    assert '<span class="source-name">nvd</span>' in page


def test_sources_that_match_beside_a_refused_one_are_not_headed_as_agreeing():
    # A heading is a claim, and a vector nobody could read may disagree with every
    # one that was, as the refused one here does.
    page = as_html(report_of(finding(DJANGO, vectors=REFUSED_DISSENT)))
    assert "Sources agree" not in page
    assert "A source was refused (1)" in page
    assert ENVIRONMENTAL_VECTOR in page
    counted = (
        "0 carry sources that disagree; 1 carries a source this calculator could not read."
    )
    assert counted in page


def test_the_page_names_the_component_a_finding_was_raised_against():
    assert "django 2.2.0" in agreements_panel(report_of(finding(DJANGO)))


def test_no_source_gets_a_column_of_its_own():
    # A column headed `nvd` would be empty on 14 of the 18 findings under test, so
    # the table's headers are generic and each source is a row.
    page = agreements_panel(report_of(finding(DJANGO, vectors={"ghsa": CONFIDENTIALITY_ONLY})))
    assert "nvd" not in page
    assert "<th>ghsa" not in page and "<th>nvd" not in page


def test_an_advisory_link_is_the_only_address_on_the_page_and_nothing_fetches_it():
    # A reader follows a link or does not; a script or a stylesheet would be
    # fetched on opening, which a scan run offline cannot afford.
    page = as_html(report_of(finding(DJANGO, url=ADVISORY_URL)))
    assert page.count("https://") == 1 and f'<a href="{ADVISORY_URL}"' in page
    assert "<link" not in page and " src=" not in page


def test_the_explanation_disclosure_is_stated_once_where_a_model_explained():
    # The model's prose is unchecked and computes nothing; the disclosure that
    # says so is rendered once, above the contested cards, when an explanation exists.
    page = disagreements_panel(explained_report())
    assert "Written by a model from the advisory text" in page
    assert "no score or ruling is computed from it" in page
    assert page.count("Written by a model from the advisory text") == 1


def test_a_run_with_no_explanation_states_no_disclosure():
    page = disagreements_panel(report_of(disagreeing()))
    assert "Written by a model from the advisory text" not in page
