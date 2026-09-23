"""Guards on the council's projection into the report: the states kept apart, and grouped once.

The projection's whole job is that a reader can tell four things apart -- a
council that settled a vector, one that ran and could not, a finding it was never
put to, and a run where nobody was named to ask. The last two used to be the same
absence, which said no council had run on a finding a council had deliberately
passed over.
"""

import pytest

from report.council_record import (
    CouncilAssessment,
    CouncilNotAsked,
    CouncilWithoutVector,
    grouped_by_reason,
    was_assessed,
)

AGREED = "no published source disagrees, so there is nothing to reconcile"
NO_TEXT = "the advisory carries no text for a member to read"


def test_a_skip_that_says_no_reason_is_refused():
    # An unexplained skip reads on a report as an oversight, and this one is a
    # decision the run made.
    with pytest.raises(ValueError, match="no reason was recorded"):
        CouncilNotAsked("CVE-1", "")


def test_a_finding_passed_over_is_not_a_finding_that_was_assessed():
    assert was_assessed(CouncilNotAsked("CVE-1", AGREED)) is False
    assert was_assessed(CouncilAssessment("CVE-1", "CVSS:3.1/AV:N", False)) is True
    assert was_assessed(CouncilWithoutVector("CVE-1", False)) is True


def test_the_findings_passed_over_are_grouped_by_the_reason_they_were():
    passed = [
        CouncilNotAsked("CVE-3", AGREED),
        CouncilNotAsked("CVE-1", NO_TEXT),
        CouncilNotAsked("CVE-2", AGREED),
    ]
    # By reason, so two runs group identically; the findings under one reason
    # stay in the order the record holds them.
    grouped = grouped_by_reason(passed)
    assert [one.because for one in grouped] == [AGREED, NO_TEXT]
    assert [one.advisory_ids for one in grouped] == [("CVE-3", "CVE-2"), ("CVE-1",)]


def test_grouping_nothing_gives_nothing_rather_than_an_empty_reason():
    assert grouped_by_reason([]) == ()
