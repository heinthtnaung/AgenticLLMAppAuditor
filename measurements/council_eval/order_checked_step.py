"""The `order-checked` step: every roster, each member counting only values both orders give.

For each roster it prints what `score` prints -- totals, metrics against R1 and
the baseline, members and vectors -- and two tables more: each member's
verdicts by metric, and the values that survived beside the option the
product's order lists last. No model is asked.
"""

import argparse
from collections import Counter
from itertools import product
from pathlib import Path
from typing import Any

from cvss.metrics import METRIC_ORDER

from council_eval.compose import pass_models, rosters
from council_eval.dataset import Item, read_dataset
from council_eval.inspections import named_value_lines
from council_eval.measures import member_measures, metric_measures
from council_eval.named_values import named_values
from council_eval.order_checked import VERDICTS, Verdict, order_checked_roster
from council_eval.replies import Replies, read_replies
from council_eval.tables import (
    header_lines,
    member_table,
    metric_table,
    table,
    totals_lines,
    vector_table,
)
from council_eval.variants import BASELINE
from council_eval.vectors import vector_measures

VERDICT_COLUMNS = ("member", "metric", *VERDICTS)


def add_order_checked(commands: Any) -> None:
    """Add the step that scores every roster with each member's two orders held to each other."""
    helped = "score every roster, a value kept only where both orders agree"
    step = commands.add_parser("order-checked", help=helped)
    step.add_argument("--dataset", type=Path, required=True)
    step.add_argument("--forward", type=Path, nargs="+", required=True)
    step.add_argument("--reversed", type=Path, nargs="+", required=True)
    step.set_defaults(run=run_order_checked)


def run_order_checked(options: argparse.Namespace) -> int:
    """Score every roster the product-order passes build, each member held to its reversed pass."""
    items = read_dataset(options.dataset)
    forward, reversed_ = read_replies(tuple(options.forward)), read_replies(tuple(options.reversed))
    print("\n".join(header_lines((*forward.headers, *reversed_.headers))))
    for roster in rosters(pass_models(forward)):
        print("\n".join(checked_roster_lines(items, roster, forward, reversed_)))
    return 0


def checked_roster_lines(
    items: tuple[Item, ...], roster: tuple[str, ...], forward: Replies, reversed_: Replies
) -> list[str]:
    """Give one order-checked roster's section: totals, metrics, members, verdicts, values."""
    outcomes, verdicts = order_checked_roster(items, roster, forward, reversed_)
    return [
        "", f"ROSTER {' + '.join(roster)}, order-checked  ({len(items)} items)",
        *totals_lines(outcomes),
        "", *metric_table(metric_measures(items, outcomes)),
        "", *member_table(member_measures(outcomes)),
        "", *verdict_table(verdicts, roster),
        "", *named_value_lines(named_values(outcomes, BASELINE)),
        "", *vector_table(vector_measures(items, outcomes)),
    ]


def verdict_table(verdicts: list[Verdict], roster: tuple[str, ...]) -> list[str]:
    """Lay out how often each member's two orders agreed, differed, declined or failed."""
    counted = Counter((model, metric, verdict) for _, model, metric, verdict in verdicts)
    pairs = product(roster, METRIC_ORDER)
    return table(VERDICT_COLUMNS, [verdict_row(counted, model, metric) for model, metric in pairs])


def verdict_row(counted: Counter, model: str, metric: str) -> list[Any]:
    """Give one member's row on one metric: how many findings got each verdict."""
    return [model, metric, *[counted[(model, metric, verdict)] for verdict in VERDICTS]]
