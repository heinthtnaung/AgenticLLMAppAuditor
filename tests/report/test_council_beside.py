"""Guards on the council's figure: its settled vector on the CVSS scale, beside the score."""

from council_runs import DISSENTING, council_ran, passed_over_entirely
from report.council_beside import (
    COUNCIL_SOURCE, CouncilFigure, banded, council_figure, figure_label, figure_of,
)
from report.record import build_report
from report_samples import LOW_CONFIDENTIALITY, PROVENANCE, TOTAL_LOSS, catalogue, component

ADVISORY_ID = "CVE-2019-14234"


def figure_of(*council) -> CouncilFigure | None:
    """Give the council's figure for one advisory in a record carrying these council entries."""
    report = build_report(PROVENANCE, catalogue(component()), (), {}, council)
    return council_figure(report, ADVISORY_ID)


def test_a_council_that_settled_a_vector_gives_that_vector_and_its_cvss_base_score():
    # The members answer every metric with its legal value, which is TOTAL_LOSS.
    assert figure_of(council_ran(ADVISORY_ID)) == CouncilFigure(TOTAL_LOSS, 9.8)


def test_a_council_that_settled_no_vector_gives_no_figure():
    assert figure_of(council_ran(ADVISORY_ID, **DISSENTING)) is None


def test_a_finding_the_council_passed_over_gives_no_figure():
    report = build_report(PROVENANCE, catalogue(), (), {}, passed_over_entirely())
    assert council_figure(report, "CVE-PASSED") is None


def test_a_run_with_no_council_gives_no_figure():
    assert figure_of() is None


def test_the_figure_is_named_as_the_councils_and_on_the_cvss_scale():
    # Named as every rendering names it, and with its scale, because beside a
    # 0-100 organisation score a bare 9.8 reads as one.
    assert figure_label(CouncilFigure(TOTAL_LOSS, 9.8)) == f"{COUNCIL_SOURCE} CVSS 9.8"


def test_the_figure_is_worked_out_from_the_councils_record_alone():
    # Without a report, because the council's own entry has only its record.
    assert figure_of(council_ran(ADVISORY_ID)) == CouncilFigure(TOTAL_LOSS, 9.8)


def test_the_figure_carries_the_cvss_band_its_base_score_lands_in():
    assert CouncilFigure(TOTAL_LOSS, 9.8).band == "Critical"
    assert CouncilFigure(LOW_CONFIDENTIALITY, 5.3).band == "Medium"


def test_the_council_entry_says_the_figure_with_its_scale_and_band():
    assert banded(CouncilFigure(TOTAL_LOSS, 9.8)) == "CVSS 9.8 Critical"
