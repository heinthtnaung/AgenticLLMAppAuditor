"""The evaluation's checks on its own evidence: reruns, quotations, and the server's own log.

None of these asks a model. `compare` sets two saved passes of one model side
by side, `quoting` reads what the members of the passes quoted, and
`server-log` and `turns` read Ollama's journal for requests no pass made.
"""

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from report.council_record import CouncilOutcome

from council_eval.compose import pass_models, replay_roster
from council_eval.dataset import read_dataset
from council_eval.quoting import prompt_quoted_by_member, sole_by_member, unverified_by_member
from council_eval.replies import CallKey, read_replies
from council_eval.reruns import RerunComparison, compare_passes
from council_eval.server_log import (
    Load,
    Request,
    excerpt_lines,
    irregular_turns,
    read_excerpt,
    turn_count,
)
from council_eval.tables import table

NONE = "none"
METRICS_PER_TURN = 8
QUOTING_COLUMNS = (
    "member", "settled on its quotation alone", "unverified", "of which the prompt's",
)
PROMPT_COLUMNS = ("member", "metric", "prompt quoted")


def add_inspections(commands: Any) -> None:
    """Add the four subcommands that check the evaluation's evidence."""
    compare = commands.add_parser("compare", help="compare two passes of one model byte for byte")
    compare.add_argument("--first", type=Path, required=True)
    compare.add_argument("--second", type=Path, required=True)
    compare.set_defaults(run=run_compare)
    quoting = commands.add_parser("quoting", help="whose quotation settled alone; quoted prompt")
    quoting.add_argument("--dataset", type=Path, required=True)
    quoting.add_argument("--replies", type=Path, nargs="+", required=True)
    quoting.set_defaults(run=run_quoting)
    log = commands.add_parser("server-log", help="keep a journal's requests and loads")
    log.add_argument("--journal", type=Path, required=True)
    log.add_argument("--out", type=Path, required=True)
    log.set_defaults(run=run_server_log)
    turns = commands.add_parser("turns", help="count a server log's turns and name odd ones")
    turns.add_argument("--excerpt", type=Path, required=True)
    turns.add_argument("--calls", type=int, default=METRICS_PER_TURN)
    turns.set_defaults(run=run_turns)


def run_compare(options: argparse.Namespace) -> int:
    """Compare two passes of one model, call by call."""
    first, second = read_replies((options.first,)), read_replies((options.second,))
    print("\n".join(comparison_lines(compare_passes(first, second))))
    return 0


def comparison_lines(found: RerunComparison) -> list[str]:
    """Say how two passes compare, and name every call that differed or was reloaded."""
    return [
        f"{found.model}: {found.calls} calls, {found.same_request} with the same request, "
        f"{found.identical} byte-identical replies, {found.unanswered} unanswered in either",
        f"  differing: {named(found.differing)}",
        f"  reloaded after an item's first call, first pass: {named(found.reloaded_first)}",
        f"  reloaded after an item's first call, second pass: {named(found.reloaded_second)}",
    ]


def named(keys: tuple[CallKey, ...]) -> str:
    """Name calls by item and metric, or `NONE`."""
    return ", ".join(f"{key} {metric}" for key, _, metric in keys) or NONE


def run_quoting(options: argparse.Namespace) -> int:
    """Replay the passes' models as one roster, and say what its members quoted."""
    items, replies = read_dataset(options.dataset), read_replies(tuple(options.replies))
    print("\n".join(quoting_lines(replay_roster(items, pass_models(replies), replies))))
    return 0


def quoting_lines(outcomes: tuple[CouncilOutcome, ...]) -> list[str]:
    """Lay out each member's lone settlements and quoted prompt, then quoted prompt by metric."""
    sole, unverified = sole_by_member(outcomes), unverified_by_member(outcomes)
    prompt = prompt_quoted_by_member(outcomes)
    members = sorted({*sole, *unverified, *(member for member, _ in prompt)})
    rows = [[who, sole[who], unverified[who], prompt_total(prompt, who)] for who in members]
    by_metric = [[who, metric, count] for (who, metric), count in sorted(prompt.items())]
    return [*table(QUOTING_COLUMNS, rows), "", *table(PROMPT_COLUMNS, by_metric)]


def prompt_total(prompt: Counter, member: str) -> int:
    """Count one member's unverified quotations that are the prompt, over every metric."""
    return sum(count for (who, _), count in prompt.items() if who == member)


def run_server_log(options: argparse.Namespace) -> int:
    """Keep a journal's request and load lines in a new excerpt file."""
    kept = excerpt_lines(options.journal.read_text(encoding="utf-8"))
    with options.out.open("x", encoding="utf-8") as out:
        out.write("\n".join(kept) + "\n")
    print(f"{len(kept)} lines kept in {options.out}")
    return 0


def run_turns(options: argparse.Namespace) -> int:
    """Say what a server log holds, and name every turn of an unexpected size."""
    requests, loads = read_excerpt(options.excerpt.read_text(encoding="utf-8"))
    print("\n".join(turn_lines(requests, loads, options.calls)))
    return 0


def turn_lines(requests: tuple[Request, ...], loads: tuple[Load, ...], calls: int) -> list[str]:
    """Count requests by path and loads by model, and name the turns not of `calls` calls."""
    paths = Counter(f"{one.method} {one.path}" for one in requests)
    models = Counter(one.model for one in loads)
    odd = ", ".join(f"{time} ({size})" for time, size in irregular_turns(requests, calls))
    return [
        "requests: " + ", ".join(f"{count} {path}" for path, count in sorted(paths.items())),
        "loads: " + ", ".join(f"{count} {model}" for model, count in models.items()),
        f"turns: {turn_count(requests)}; not of {calls} calls: {odd or NONE}",
    ]
