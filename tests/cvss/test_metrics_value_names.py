"""Guard on the value-name table: each readable metric's values named as the specification does.

Written out from the specification rather than imported from the module under test,
for the reason `test_metrics.py` gives: a table read out of `metrics.py` would only
prove the file equals itself. A report reads these names for its tooltips, and a
drift would surface only as a silently wrong or missing word, so this module fails
the day `VALUE_NAMES` parts from CVSS v3.1 or from the metric tables beside it.
"""

import pytest

from cvss.metrics import BASE_METRICS, READABLE_METRICS, TEMPORAL_METRICS, VALUE_NAMES

# CVSS v3.1 specification, sections 2 and 3: the name in words of every value of
# every metric a published vector may carry, each inner mapping in the order the
# specification prints the values. "Adjacent" and not "Adjacent Network": v3.1
# shortened the AV:A metric value name that v3.0 still spells out.
SPECIFICATION = {
    "AV": {"N": "Network", "A": "Adjacent", "L": "Local", "P": "Physical"},
    "AC": {"L": "Low", "H": "High"},
    "PR": {"N": "None", "L": "Low", "H": "High"},
    "UI": {"N": "None", "R": "Required"},
    "S": {"U": "Unchanged", "C": "Changed"},
    "C": {"H": "High", "L": "Low", "N": "None"},
    "I": {"H": "High", "L": "Low", "N": "None"},
    "A": {"H": "High", "L": "Low", "N": "None"},
    "E": {
        "X": "Not Defined", "H": "High", "F": "Functional",
        "P": "Proof-of-Concept", "U": "Unproven",
    },
    "RL": {
        "X": "Not Defined", "U": "Unavailable", "W": "Workaround",
        "T": "Temporary Fix", "O": "Official Fix",
    },
    "RC": {"X": "Not Defined", "C": "Confirmed", "R": "Reasonable", "U": "Unknown"},
}

METRIC_CASES = [
    pytest.param(metric, id=metric.abbreviation)
    for metric in (*BASE_METRICS, *TEMPORAL_METRICS)
]


def test_the_value_names_are_the_specification_word_for_word():
    # Equality, not containment: a renamed value ("Netwrk") or a stray metric would
    # both show as a wrong or absent tooltip and nowhere else.
    assert VALUE_NAMES == SPECIFICATION


def test_the_table_names_exactly_the_readable_metrics():
    # A name for an unreadable metric could never be reached; a missing one leaves a
    # legal vector with a plain, untitled field.
    assert set(VALUE_NAMES) == set(READABLE_METRICS)


@pytest.mark.parametrize("metric", METRIC_CASES)
def test_each_metric_names_exactly_its_values_no_missing_no_extra(metric):
    # The letters a value can take live in `metric.values`; the letters that have a
    # name live in VALUE_NAMES. They must be the same set, or a value renders untitled.
    assert set(VALUE_NAMES[metric.abbreviation]) == set(metric.values)


@pytest.mark.parametrize("metric", METRIC_CASES)
def test_each_metric_names_its_values_in_value_order(metric):
    # `metric.values` order is quoted back in refusals and drives the canonical
    # spelling; the name table follows it so the two never read out of step.
    assert tuple(VALUE_NAMES[metric.abbreviation]) == metric.values
