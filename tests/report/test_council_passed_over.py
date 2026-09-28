"""Guards on the findings a council passed over: grouped by reason once, for every rendering."""

from cli.council_run import NO_TEXT_TO_READ, SOURCES_AGREE
from report.council_passed_over import grouped_by_reason
from report.council_record import CouncilNotAsked


def test_the_findings_passed_over_are_grouped_by_the_reason_they_were():
    passed = [
        CouncilNotAsked("CVE-3", SOURCES_AGREE),
        CouncilNotAsked("CVE-1", NO_TEXT_TO_READ),
        CouncilNotAsked("CVE-2", SOURCES_AGREE),
    ]
    # By reason, so two runs group identically; the findings under one reason
    # stay in the order the record holds them.
    grouped = grouped_by_reason(passed)
    assert [one.because for one in grouped] == [SOURCES_AGREE, NO_TEXT_TO_READ]
    assert [one.advisory_ids for one in grouped] == [("CVE-3", "CVE-2"), ("CVE-1",)]


def test_grouping_nothing_gives_nothing_rather_than_an_empty_reason():
    assert grouped_by_reason([]) == ()
