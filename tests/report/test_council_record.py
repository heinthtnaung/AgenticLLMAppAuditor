"""Guards on the council's projection into the report: the states kept apart, and grouped once.

The projection's whole job is that a reader can tell four things apart -- a
council that settled a vector, one that ran and could not, a finding it was never
put to, and a run where nobody was named to ask. Recording the last two as one
absence would say no council had run on a finding a council deliberately passed
over.
"""

from typing import get_args

import pytest

from cli.council_run import NO_TEXT_TO_READ, SOURCES_AGREE
from council_runs import DISSENTING, council_ran, council_states
from report.council_record import (
    CouncilAssessment,
    CouncilNotAsked,
    CouncilOutcome,
    CouncilWithoutVector,
    grouped_by_reason,
    was_assessed,
)


def test_a_skip_that_says_no_reason_is_refused():
    # An unexplained skip reads on a report as an oversight, and this one is a
    # decision the run made.
    with pytest.raises(ValueError, match="no reason was recorded"):
        CouncilNotAsked("CVE-1", "")


def test_a_finding_passed_over_is_not_a_finding_that_was_assessed():
    settled, still_open = council_ran(), council_ran(**DISSENTING)
    assert (type(settled), type(still_open)) == (CouncilAssessment, CouncilWithoutVector)
    assert was_assessed(CouncilNotAsked("CVE-1", SOURCES_AGREE)) is False
    assert was_assessed(settled) is True
    assert was_assessed(still_open) is True


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


def test_the_states_every_renderer_is_shown_are_every_state_the_record_can_hold():
    # Each renderer's test renders `council_states()`. A type added to the union
    # and missing there reaches a rendering first as an `AttributeError` in a run.
    assert {type(one) for one in council_states()} == set(get_args(CouncilOutcome))
