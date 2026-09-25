"""The evaluation's four steps as subcommands: freeze a dataset, collect a pass, gate, score.

Only `collect` asks a model. `dataset` runs Syft and Trivy offline, and `gate`
and `score` replay saved passes through the product's own code, so either can
be re-run as often as anyone likes without a model or a scan. The checks on the
evidence itself -- reruns, quotations, the server's log -- are
`council_eval.inspections`.
"""

import argparse
import os
from pathlib import Path
from typing import Any

from deps import syft_runner, trivy_runner
from deps.trivy_database import database_built_at, metadata_of, trivy_cache_directory
from report.council_record import CouncilAssessment, CouncilOutcome

from council_eval.collect import collect
from council_eval.compose import pass_models, replay_roster, rosters
from council_eval.contests import contest_measures
from council_eval.dataset import Item, read_dataset, vulnscout_items, write_dataset
from council_eval.gate import differences, recorded_findings, replayed_findings
from council_eval.inspections import add_inspections
from council_eval.measures import member_measures, metric_measures, outcome_totals
from council_eval.pass_provenance import pass_header
from council_eval.replies import Replies, read_replies
from council_eval.tables import (
    contest_table,
    header_lines,
    member_table,
    metric_table,
    vector_table,
)
from council_eval.vectors import vector_measures

GATE_FAILED = 1


def main(argv: list[str]) -> int:
    """Run one step of the evaluation, and give its exit code."""
    options = parser().parse_args(argv)
    return options.run(options)


def parser() -> argparse.ArgumentParser:
    """Describe the four steps, and the checks on their evidence, and what each is given."""
    top = argparse.ArgumentParser(prog="council_eval", description=__doc__.splitlines()[0])
    commands = top.add_subparsers(required=True)
    frozen = commands.add_parser("dataset", help="freeze the vulnscout findings to a file")
    frozen.add_argument("--repository", type=Path, required=True)
    frozen.add_argument("--out", type=Path, required=True)
    frozen.set_defaults(run=run_dataset)
    one_pass = commands.add_parser("collect", help="ask one model every item, saving every call")
    one_pass.add_argument("--dataset", type=Path, required=True)
    one_pass.add_argument("--model", required=True)
    one_pass.add_argument("--out", type=Path, required=True)
    one_pass.set_defaults(run=run_collect)
    gate = commands.add_parser("gate", help="replay a roster against a recorded audit report")
    gate.add_argument("--dataset", type=Path, required=True)
    gate.add_argument("--replies", type=Path, nargs="+", required=True)
    gate.add_argument("--recorded", type=Path, required=True)
    gate.set_defaults(run=run_gate)
    score = commands.add_parser("score", help="measure every roster the passes can build")
    score.add_argument("--dataset", type=Path, required=True)
    score.add_argument("--replies", type=Path, nargs="+", required=True)
    score.set_defaults(run=run_score)
    add_inspections(commands)
    return top


def run_dataset(options: Any) -> int:
    """Freeze the findings of one repository, and the scanners and database that produced them."""
    # One cache, dated and scanned with, as the audit does: two could be two databases.
    cache = trivy_cache_directory(os.environ)
    built = database_built_at(metadata_of(cache))
    if not built:
        raise ValueError(f"the Trivy database in {cache} says nothing of when it was built")
    items = vulnscout_items(options.repository.resolve(), cache)
    built_from = {
        "repository": str(options.repository),
        "syft": syft_runner.installed_version(),
        "trivy": trivy_runner.installed_version(),
        "database_built_at": built,
        "trivy_cache": str(cache),
    }
    write_dataset(items, built_from, options.out)
    print(f"{len(items)} items frozen to {options.out}")
    return 0


def run_collect(options: Any) -> int:
    """Collect one model's pass over a frozen dataset."""
    items = read_dataset(options.dataset)
    header = pass_header(options.model, options.dataset)
    calls = collect(items, options.model, options.out, header)
    print(f"{calls} calls of {options.model} saved to {options.out}")
    return 0


def run_gate(options: Any) -> int:
    """Replay the passes' models as one roster, and compare it with a recorded report."""
    items = read_dataset(options.dataset)
    replies = read_replies(tuple(options.replies))
    outcomes = replay_roster(items, pass_models(replies), replies)
    recorded = recorded_findings(options.recorded.read_text(encoding="utf-8"))
    found = differences(recorded, replayed_findings(outcomes))
    print("\n".join(totals_lines(outcomes)))
    print("\n".join(found) or "gate passed: the replay prints what the recorded audit printed")
    return GATE_FAILED if found else 0


def run_score(options: Any) -> int:
    """Measure every roster the passes can build, against R1 and the commonest-value baseline."""
    items = read_dataset(options.dataset)
    replies = read_replies(tuple(options.replies))
    print("\n".join(header_lines(replies.headers)))
    for roster in rosters(pass_models(replies)):
        print("\n".join(roster_lines(items, roster, replies)))
    return 0


def roster_lines(items: tuple[Item, ...], roster: tuple[str, ...], replies: Replies) -> list[str]:
    """Give one roster's section: its totals, and its metric, member and vector tables."""
    outcomes = replay_roster(items, roster, replies)
    return [
        "", f"ROSTER {' + '.join(roster)}  ({len(items)} items)", *totals_lines(outcomes),
        "", *metric_table(metric_measures(items, outcomes)),
        "", *contest_table(contest_measures(items, outcomes)),
        "", *member_table(member_measures(outcomes)),
        "", *vector_table(vector_measures(items, outcomes)),
    ]


def totals_lines(outcomes: tuple[CouncilOutcome, ...]) -> list[str]:
    """Count every metric by outcome, and name every vector reached."""
    totals = outcome_totals(outcomes)
    reached = [one for one in outcomes if isinstance(one, CouncilAssessment)]
    vectors = [f"  {one.advisory_id}  {one.vector}" for one in reached]
    counted = ", ".join(f"{totals[kind]} {kind}" for kind in ("settled", "contested", "unresolved"))
    return [f"{sum(totals.values())} metrics: {counted}; {len(vectors)} vectors", *vectors]
