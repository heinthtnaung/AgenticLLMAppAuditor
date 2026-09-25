"""Guards on the Temporal metric table, and on the Base metrics staying all a member may answer.

Written out from the specification rather than imported, for the reason
`test_metrics.py` gives: a table read out of `metrics.py` only proves the file
equals itself.
"""

import pytest

from cvss.metrics import (
    ENVIRONMENTAL_METRICS,
    METRIC_ORDER,
    READABLE_METRICS,
    TEMPORAL_METRICS,
    refuse_illegal_pair,
)

# CVSS v3.1 specification, section 3 (Tables 9-11), which v3.0 matches: each
# Temporal metric, its name in words, and its values in the order printed.
TEMPORAL_SPECIFICATION = {
    "E": ("Exploit Code Maturity", ("X", "H", "F", "P", "U")),
    "RL": ("Remediation Level", ("X", "U", "W", "T", "O")),
    "RC": ("Report Confidence", ("X", "C", "R", "U")),
}


def test_the_temporal_table_is_the_three_metrics_the_specification_defines():
    table = {one.abbreviation: (one.name, one.values) for one in TEMPORAL_METRICS}
    assert table == TEMPORAL_SPECIFICATION


def test_a_published_vector_may_carry_the_base_and_temporal_metrics_and_nothing_else():
    assert set(READABLE_METRICS) == {*METRIC_ORDER, *TEMPORAL_SPECIFICATION}
    assert set(ENVIRONMENTAL_METRICS).isdisjoint(READABLE_METRICS)


def test_a_council_answer_is_still_held_to_the_base_metrics_even_for_a_legal_temporal_value():
    # A published vector may carry `E:H`; a member may not answer it, because the
    # council rules on the eight Base metrics that the score is made of.
    with pytest.raises(ValueError, match="Unknown metric 'E'"):
        refuse_illegal_pair("E", "H")
