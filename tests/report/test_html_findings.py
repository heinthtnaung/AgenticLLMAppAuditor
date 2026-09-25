"""Guards on a finding's three shapes: every source a row, and no source a column.

On the repository under test NVD published a vector for 4 findings of 18, so a
layout with a column headed `nvd` is empty on 14 rows and looks right until a
real repository is on screen. What these hold is that the page renders the list
the finding carries -- and that a source nobody could read stays on the card,
marked not scored, rather than becoming a zero.
"""

from report.html_findings import (
    agreeing_section,
    contested_section,
    unchecked_section,
    unscored_section,
)
from report.html_report import as_html
from report.record import build_report
from report_samples import (
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

DJANGO = component()

# A score chip is the only place a figure goes, so its absence is the check that
# an unscored finding was not quietly given a number.
NO_CHIP = '<span class="value">'


def report_of(*findings):
    """Build a report carrying these findings and nothing else."""
    return build_report(PROVENANCE, catalogue(DJANGO), findings, {})


def disagreeing():
    """One finding two sources read differently, 5.3 against 9.8."""
    return finding(DJANGO, vectors={"ghsa": LOW_CONFIDENTIALITY, "nvd": TOTAL_LOSS})


def test_a_run_with_no_contested_finding_shows_no_contested_section():
    agreed = finding(DJANGO, vectors={"ghsa": CONFIDENTIALITY_ONLY})
    assert contested_section(report_of(agreed)) == ""


def test_every_source_is_a_row_of_its_own_with_its_own_vector():
    page = contested_section(report_of(disagreeing()))
    assert '<span class="source-name">ghsa</span>' in page
    assert '<span class="source-name">nvd</span>' in page
    assert LOW_CONFIDENTIALITY in page and TOTAL_LOSS in page


def test_each_score_is_written_beside_the_vector_it_derives_from():
    # The one rule the whole record is shaped by: a reader with the published
    # equations reproduces every number on the row beside it.
    page = contested_section(report_of(disagreeing()))
    assert page.index("5.3") < page.index(LOW_CONFIDENTIALITY)
    assert page.index("9.8") < page.index(TOTAL_LOSS)


def test_a_contested_card_says_how_far_apart_and_which_bands_that_crosses():
    page = contested_section(report_of(disagreeing()))
    assert "4.5 apart" in page
    assert "Critical and Medium" in page
    assert "differ on" in page


def test_an_agreeing_finding_gets_the_same_rows_without_a_spread():
    agreed = finding(DJANGO, vectors={"ghsa": CONFIDENTIALITY_ONLY, "nvd": CONFIDENTIALITY_ONLY})
    page = agreeing_section(report_of(agreed))
    assert '<span class="source-name">ghsa</span>' in page
    assert "apart" not in page


def test_a_finding_nobody_could_score_says_so_rather_than_showing_a_zero():
    # "Nobody scored this" and "somebody scored this 0.0" are different findings.
    nothing = finding(DJANGO, vectors={})
    page = unscored_section(report_of(nothing))
    assert "No source published a readable v3 vector." in page
    assert NO_CHIP not in page


def test_a_refused_vector_is_kept_on_the_card_marked_not_scored():
    refused = finding(DJANGO, vectors={"nvd": VERSION_2_VECTOR})
    page = unscored_section(report_of(refused))
    assert VERSION_2_VECTOR in page
    assert "not scored" in page
    assert NO_CHIP not in page


def test_a_refused_source_keeps_the_reason_the_calculator_would_not_read_it():
    refused = finding(DJANGO, vectors={"nvd": VERSION_2_VECTOR})
    assert '<span class="refusal">' in unscored_section(report_of(refused))


def test_a_scored_finding_keeps_its_refused_source_too():
    both = finding(DJANGO, vectors={"ghsa": CONFIDENTIALITY_ONLY, "nvd": VERSION_2_VECTOR})
    page = unchecked_section(report_of(both))
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
    # Decided: a refused vector cannot be compared, so it is no dissent, but the
    # finding carrying it is counted on its own rather than left unsaid.
    counted = (
        "0 carry sources that disagree; 1 carries a source this calculator could not read."
    )
    assert counted in page


def test_the_page_names_the_component_a_finding_was_raised_against():
    assert "django 2.2.0" in agreeing_section(report_of(finding(DJANGO)))


def test_no_heading_is_written_for_a_source_the_finding_does_not_carry():
    # A column headed `nvd` would be empty on 14 of the 18 findings under test.
    page = agreeing_section(report_of(finding(DJANGO, vectors={"ghsa": CONFIDENTIALITY_ONLY})))
    assert "nvd" not in page
    assert "<th" not in page
