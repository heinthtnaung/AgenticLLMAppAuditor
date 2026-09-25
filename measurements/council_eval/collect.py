"""One pass: every item put to one model through the product's own path, every call saved raw.

Each item is put through `cli.council_run.assess_one` -- the audit's own step
from a finding to a council record -- with a roster of that one model and the
recording client in place of the product's. The record it returns is not kept:
the calls are, and every roster is rebuilt from them later by `compose`.

The file is opened exclusively, so a pass never overwrites one already taken.
"""

import json
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, TextIO

from cli.council_run import OLLAMA_PROVIDER, assess_one, build_roster
from council.transport import post_json

from council_eval.dataset import Item
from council_eval.pass_provenance import now
from council_eval.recording import CallRecord, Post, RecordingClient, unload_model
from council_eval.replies import call_line
from council_eval.variants import BASELINE, Variant

END_KIND = "end"
NANOSECONDS = 1e9

AskItem = Callable[[Item, str], list[CallRecord]]


def ask_item(
    item: Item, model: str, post: Post = post_json, variant: Variant = BASELINE
) -> list[CallRecord]:
    """Put one item to one model from a fresh load, in a variant's words, and give every call."""
    unload_model(model, post)
    client = RecordingClient(post=post, variant=variant)
    assess_one(item.finding, build_roster((model,)), {OLLAMA_PROVIDER: client})
    return client.calls


def collect(
    items: tuple[Item, ...],
    model: str,
    out: Path,
    header: Mapping[str, Any],
    asking: AskItem = ask_item,
    progress: TextIO = sys.stderr,
) -> int:
    """Run one pass into a new replies file, and give the number of calls it recorded."""
    calls = 0
    with out.open("x", encoding="utf-8") as written:
        write_line(written, header)
        for index, item in enumerate(items, start=1):
            records = asking(item, model)
            write_lines(written, item.key, model, records)
            print(progress_line(index, len(items), item.key, model, records), file=progress)
            calls += len(records)
        write_line(written, {"kind": END_KIND, "ended": now(), "calls": calls})
    return calls


def write_lines(written: TextIO, key: str, model: str, records: list[CallRecord]) -> None:
    """Write one item's calls, a line each."""
    for record in records:
        write_line(written, call_line(key, model, record))


def write_line(written: TextIO, line: Mapping[str, Any]) -> None:
    """Write one JSON object as one line, flushed, so a pass killed half way keeps what it did."""
    written.write(json.dumps(line, sort_keys=True) + "\n")
    written.flush()


def progress_line(index: int, total: int, key: str, model: str, records: list[CallRecord]) -> str:
    """Say which item a pass has reached, how long it took, and how long the model took to load."""
    seconds = sum(record.seconds for record in records)
    return (
        f"collect {index}/{total}  {key}  {model}  {len(records)} calls  {seconds:.1f} s  "
        f"first load {first_load_seconds(records):.1f} s"
    )


def first_load_seconds(records: list[CallRecord]) -> float:
    """Give how long an item's first call spent loading the model: long after a fresh load."""
    if not records or not isinstance(records[0].envelope, Mapping):
        return 0.0
    return records[0].envelope.get("load_duration", 0) / NANOSECONDS
