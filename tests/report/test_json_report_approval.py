"""Guards on the approval mark in the audit artefact: on every finding, and counted in the run."""

import json

import pytest

from approval_runs import EXPOSED, approval_report
from report.json_report import as_json

BOTH = ["a High or Critical Organisation Risk Score", "sources that disagree"]


def written(answers=None) -> dict:
    """Write one record of every kind of finding and read the JSON back."""
    return json.loads(as_json(approval_report(answers)))


@pytest.mark.parametrize("position, needed, reasons", [
    (0, True, BOTH), (1, True, BOTH[:1]), (2, False, []),
])
def test_every_finding_carries_whether_it_needs_approval_and_why(position, needed, reasons):
    marked = written(EXPOSED)["findings"][position]
    assert (marked["needs_approval"], marked["approval_reasons"]) == (needed, reasons)


def test_the_run_counts_the_findings_needing_approval():
    assert written(EXPOSED)["run"]["findings_needing_approval"] == 2


def test_with_no_answers_only_the_disagreeing_finding_is_marked():
    record = written()
    assert [one["needs_approval"] for one in record["findings"]] == [True, False, False]
    assert record["run"]["findings_needing_approval"] == 1
