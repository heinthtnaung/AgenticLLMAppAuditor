"""Guards on the tables: no rate without its sample, and none at all over an empty one."""

import eval_samples  # noqa: F401  (puts the evaluation package on the path)
from council_eval.measures import MetricMeasure
from council_eval.tables import NO_RATE, lift, metric_row, pass_lines, rate, table


def measured(agreed: int, majority_hits: int, scored: int) -> MetricMeasure:
    """Build one metric's measure with the counts that decide its rates."""
    return MetricMeasure(
        metric="AV", items=10, settled=8, contested=1, unresolved=1, reference_items=9,
        scored=scored, agreed=agreed, majority_value="N", majority_hits=majority_hits,
        unreferenced=8 - scored, values_used=("L", "N"),
    )


def test_a_rate_is_printed_with_its_interval():
    assert rate(5, 10) == "0.50 [0.24, 0.76]"


def test_a_rate_over_nothing_is_no_rate_and_not_zero():
    assert rate(0, 0) == NO_RATE


def test_lift_is_the_rate_less_the_commonest_value_s_rate_on_the_same_items():
    assert lift(measured(agreed=3, majority_hits=6, scored=6)) == "-0.50"
    assert lift(measured(agreed=6, majority_hits=3, scored=6)) == "+0.50"


def test_lift_over_nothing_scored_is_no_rate():
    assert lift(measured(agreed=0, majority_hits=0, scored=0)) == NO_RATE


def test_a_metric_row_carries_every_count_beside_the_rates():
    row = metric_row(measured(agreed=3, majority_hits=6, scored=6))
    assert row == ["AV", 8, 1, 1, 9, 6, 3, "0.50 [0.19, 0.81]", "N", "1.00", "-0.50", 2, "L,N"]


def test_columns_are_as_wide_as_their_widest_cell():
    assert table(("a", "bb"), [("ccc", "d")]) == ["a    bb", "ccc  d"]


def test_a_pass_names_its_pinning_and_how_much_was_uncommitted():
    lines = pass_lines({"model": "m", "seed": 11, "think": False, "changes": [" M src/x.py"]})
    assert "  seed: 11" in lines and "  think: False" in lines
    assert lines[-1] == "  uncommitted at launch: 1 paths"
