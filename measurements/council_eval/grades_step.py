"""The `grades` step: for every roster, how far its vectors land from R1 in severity bands.

Given the passes `score` is given, it rebuilds every roster as `score` does;
given the two sets `order-checked` is given, it rebuilds every roster as that
step does, each member held to both orders. Either way it prints, per roster,
the vectors counted exact, adjacent and major (`council_eval.grades`), and adds
nothing to any output the other steps print. No model is asked.
"""

import argparse
from pathlib import Path
from typing import Any

from report.council_record import CouncilOutcome

from council_eval.compose import pass_models, replay_roster, rosters
from council_eval.dataset import Item, read_dataset
from council_eval.grades import grade_lines
from council_eval.order_checked import order_checked_roster
from council_eval.replies import Replies, read_replies
from council_eval.tables import header_lines
from council_eval.vectors import vector_measures

ORDER_CHECKED = ", order-checked"


def add_grades(commands: Any) -> None:
    """Add the step that grades every roster's vectors against R1's severity band."""
    step = commands.add_parser("grades", help="count every roster's vectors by bands from R1")
    step.add_argument("--dataset", type=Path, required=True)
    step.add_argument("--replies", type=Path, nargs="+", help="passes in one order, as `score`")
    step.add_argument("--forward", type=Path, nargs="+", help="the product-order passes")
    step.add_argument("--reversed", type=Path, nargs="+", help="the reversed passes")
    step.set_defaults(run=run_grades)


def run_grades(options: argparse.Namespace) -> int:
    """Grade every roster the passes build, unchecked or order-checked by what was given."""
    refuse_mixed_inputs(options)
    items = read_dataset(options.dataset)
    if options.replies:
        return print_unchecked(items, read_replies(tuple(options.replies)))
    forward, reversed_ = read_replies(tuple(options.forward)), read_replies(tuple(options.reversed))
    return print_checked(items, forward, reversed_)


def refuse_mixed_inputs(options: argparse.Namespace) -> None:
    """Refuse anything but one set of passes, or both halves of an order-checked pair."""
    paired = bool(options.forward) and bool(options.reversed)
    if bool(options.replies) == paired or bool(options.forward) != bool(options.reversed):
        raise ValueError("give --replies, or --forward with --reversed, and not both")


def print_unchecked(items: tuple[Item, ...], replies: Replies) -> int:
    """Grade every roster the passes build in one order."""
    print("\n".join(header_lines(replies.headers)))
    for roster in rosters(pass_models(replies)):
        outcomes = replay_roster(items, roster, replies)
        print("\n".join(roster_lines(items, roster, outcomes, "")))
    return 0


def print_checked(items: tuple[Item, ...], forward: Replies, reversed_: Replies) -> int:
    """Grade every roster the product-order passes build, each member held to its reversed pass."""
    print("\n".join(header_lines((*forward.headers, *reversed_.headers))))
    for roster in rosters(pass_models(forward)):
        outcomes, _ = order_checked_roster(items, roster, forward, reversed_)
        print("\n".join(roster_lines(items, roster, outcomes, ORDER_CHECKED)))
    return 0


def roster_lines(
    items: tuple[Item, ...], roster: tuple[str, ...],
    outcomes: tuple[CouncilOutcome, ...], checked: str,
) -> list[str]:
    """Give one roster's section: its name, then its vectors graded against R1."""
    heading = f"ROSTER {' + '.join(roster)}{checked}  ({len(items)} items)"
    return ["", heading, *grade_lines(vector_measures(items, outcomes))]
