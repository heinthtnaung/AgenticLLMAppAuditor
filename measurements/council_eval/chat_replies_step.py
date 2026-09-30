"""The `chat-replies` step: a folder of replies pasted back from a chat, written as two passes.

Every reply is read (`chat_reply_file`, `chat_reply`) and matched to the prompt it
names (`chat_passes`) before either pass is written, so a refusal leaves nothing
behind. The forward replies become one pass and the reversed another, in the
shape `collect` writes, and `score`, `order-checked` and `grades` then take them
as they take any pass. Nothing here asks a model.
"""

import argparse
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from cvss.metrics import METRIC_ORDER

from council_eval.chat_outputs import refuse_unwritable
from council_eval.chat_pass_lines import (
    BROWSING_UNCHECKED,
    CHAT_PROVENANCE,
    ONE_MESSAGE,
    pass_lines,
)
from council_eval.chat_passes import AnsweredPrompt, answered_prompts
from council_eval.chat_prompt import FORWARD, REVERSED
from council_eval.chat_prompt_set import chat_prompts
from council_eval.chat_reply import ChatReply, read_chat_reply
from council_eval.chat_reply_file import read_saved_reply
from council_eval.chat_summary import (
    ORDER_VERDICTS,
    QUOTATION_KINDS,
    order_verdicts,
    quotation_counts,
)
from council_eval.collect import write_line
from council_eval.dataset import read_dataset
from council_eval.pass_provenance import file_digest, git_output
from council_eval.tables import table
from council_eval.variants import CHAT, CHAT_REVERSED

REPLY_SUFFIX = ".txt"
TEXT_ENCODING = "utf-8"
ORDERS = (FORWARD, REVERSED)


def add_chat_replies(commands: Any) -> None:
    """Add the step that turns replies pasted back from a chat into two passes."""
    helped = "write a folder of replies pasted from a chat as a forward and a reversed pass"
    step = commands.add_parser("chat-replies", help=helped)
    step.add_argument("--dataset", type=Path, required=True)
    step.add_argument("--replies", type=Path, required=True, help="the folder of saved replies")
    step.add_argument("--forward-out", type=Path, required=True)
    step.add_argument("--reversed-out", type=Path, required=True)
    step.set_defaults(run=run_chat_replies)


def run_chat_replies(options: argparse.Namespace) -> int:
    """Read, match and check every reply, then write the two passes, refusing to overwrite."""
    outs = (options.forward_out, options.reversed_out)
    refuse_unwritable(outs)
    prompts = chat_prompts(read_dataset(options.dataset))
    answered = answered_prompts(prompts, read_replies_folder(options.replies))
    digest = file_digest(options.dataset)
    passes = [pass_lines(answered, one, digest, git_output) for one in (CHAT, CHAT_REVERSED)]
    for out, lines in zip(outs, passes):
        write_pass(out, lines)
    print("\n".join(import_lines(answered, outs)))
    return 0


def read_replies_folder(folder: Path) -> tuple[ChatReply, ...]:
    """Read every reply in a folder that holds replies and nothing else."""
    files = sorted(folder.iterdir())
    strays = [one.name for one in files if one.suffix != REPLY_SUFFIX or not one.is_file()]
    if strays:
        raise ValueError(f"{folder} holds {', '.join(strays)}; a replies folder holds replies only")
    if not files:
        raise ValueError(f"{folder} holds no replies")
    return tuple(read_chat_reply(read_saved_reply(one)) for one in files)


def write_pass(out: Path, lines: list[Mapping[str, Any]]) -> None:
    """Write one pass as JSON Lines into a new file."""
    with out.open("x", encoding=TEXT_ENCODING) as written:
        for line in lines:
            write_line(written, line)


def import_lines(answered: tuple[AnsweredPrompt, ...], outs: tuple[Path, ...]) -> list[str]:
    """Say what was imported and what it cannot show, then the quotations and the orders."""
    first = answered[0].reply.saved
    dates = sorted(one.reply.saved.date for one in answered)
    calls = len(answered) // len(ORDERS) * len(METRIC_ORDER)
    return [
        f"chat-replies: {len(answered)} replies of {first.model!r} through "
        f"{first.interface!r}, dated {dates[0]} to {dates[-1]}",
        f"  prompt: {CHAT.prompt_version} and {CHAT_REVERSED.prompt_version}: {ONE_MESSAGE}",
        f"  provenance: {CHAT_PROVENANCE}",
        f"  web browsing: {BROWSING_UNCHECKED}",
        *(f"  {order} pass: {calls} calls written to {out}" for order, out in zip(ORDERS, outs)),
        "", *table(("order", *QUOTATION_KINDS), quotation_rows(quotation_counts(answered))),
        "", *table(("metric", *ORDER_VERDICTS), verdict_rows(order_verdicts(answered))),
    ]


def quotation_rows(counted: Counter) -> list[list[Any]]:
    """Give, per order, what the replies offered and how many quotations held."""
    return [[order, *counts_of(counted, order, QUOTATION_KINDS)] for order in ORDERS]


def verdict_rows(counted: Counter) -> list[list[Any]]:
    """Give, per metric, how many advisories' orders were stable, order-sensitive or declined."""
    return [[metric, *counts_of(counted, metric, ORDER_VERDICTS)] for metric in METRIC_ORDER]


def counts_of(counted: Counter, row: str, columns: tuple[str, ...]) -> list[int]:
    """Give one row's counts, a column each."""
    return [counted[(row, column)] for column in columns]
