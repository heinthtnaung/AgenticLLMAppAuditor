"""Score the recorded explainer calls from their saved replies alone, naming the code that scored.

Each saved `response` is replayed through the product's `council.explanation.explain`
against the finding rebuilt from the frozen dataset, and every figure printed comes from
that replay: it is what the explainer's current reading makes of the replies. The outcome
each call recorded when it was made is compared, and a call whose replay differs is named.

The first line names the files that read and sort a reply, and the metric table the reading
looks a metric's name up in, by their git blob ids, so the summary says which reading
produced it; `git log --find-object=ID` finds the commits that hold one. The `metric`
strings are read from the raw reply, before the parser reads them.

`--write` re-scores this record in one step: it rewrites `summary.txt`, and the README's
scored block between its two markers, which shows the summary's scoring and counts.

    python measurements/explainer_vulnscout/summary.py --write
    python measurements/explainer_vulnscout/summary.py \\
        measurements/explainer_vulnscout/replies.jsonl
"""

import argparse
import hashlib
import json
import sys
from collections import Counter
from itertools import chain, product
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import council.explanation as sorting  # noqa: E402
import council.explanation_reply as reading  # noqa: E402
import cvss.metrics as naming  # noqa: E402
from cli.council_run import advisory_text  # noqa: E402
from cli.explanation_run import published_on  # noqa: E402
from council.explanation import explain  # noqa: E402
from council.providers import ollama_member  # noqa: E402
from council.reply_object import extract_object  # noqa: E402
from council_eval.dataset import read_dataset  # noqa: E402
from explainer_vulnscout.probe import DATASET, outcome_of  # noqa: E402

Line = dict[str, Any]
KINDS = {True: "one-metric", False: "multi-metric"}
SCORING_CODE = {
    "src/council/explanation_reply.py": reading,
    "src/council/explanation.py": sorting,
    "src/cvss/metrics.py": naming,
}
RECORD = Path(__file__).resolve().parent
REPLIES = "replies.jsonl"
SUMMARY = "summary.txt"
README = "README.md"
# The README's copy of the summary's scoring and counts sits between these, as a text block.
BLOCK_BEGIN = "<!-- scored: begin -->\n```text\n"
BLOCK_END = "```\n<!-- scored: end -->"
# The summary's three sections, scoring, rows and counts, are split by a blank line.
SECTION = "\n\n"
WRITE_HELP = "rewrite this record's summary.txt and its README's scored block"


def recorded_calls(path: Path) -> tuple[dict[str, Any], list[Line]]:
    """Read a probe's file into its header and its calls."""
    lines = [json.loads(one) for one in path.read_text(encoding="utf-8").splitlines()]
    return lines[0]["header"], lines[1:]


def blob_id(module: Any) -> str:
    """Give the git blob id of a module's source, as `git hash-object` would."""
    source = Path(module.__file__).read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(source) + source).hexdigest()


def replayed(line: Line, findings: dict[str, Any]) -> dict[str, Any]:
    """Give the outcome the product makes of one saved reply, with no model called."""
    reply = line["envelope"]["response"]
    finding = findings[line["advisory_id"]]
    clients = {"ollama": lambda member, prompt: reply}
    explainer = ollama_member(line["model"])
    return outcome_of(explain(advisory_text(finding), published_on(finding), explainer, clients))


def metrics_as_written(line: Line) -> list[str]:
    """Give each item's `metric` exactly as the model wrote it."""
    return [repr(one["metric"]) for one in extract_object(line["envelope"]["response"])["items"]]


def row(line: Line) -> str:
    """Give one scored call as a line: finding, kept, each drop and why, the metrics as written."""
    outcome = line["scored"]
    drops = "; ".join(f"{one['metric']!r} {one['reason']}, quotation found {one['quotation_found']}"
                      for one in outcome["dropped"]) or "-"
    return (f"{line['model']:14} seed {line['seed']}  {line['advisory_id']:15} "
            f"{','.join(line['metrics']):6} kept {len(outcome['kept'])}/{len(line['metrics'])}  "
            f"dropped: {drops}  written: {', '.join(metrics_as_written(line))}")


def drop_reasons(line: Line) -> list[str]:
    """Give why each item one scored call offered was not kept."""
    return [drop["reason"] for drop in line["scored"]["dropped"]]


def tally(model: str, one_metric: bool, calls: list[Line]) -> str:
    """Count one model's scored calls on one kind of finding: explained, kept, drops by reason."""
    own = [one for one in calls if one["model"] == model and one["one_metric"] == one_metric]
    drops = Counter(chain.from_iterable(map(drop_reasons, own)))
    kept = sum(len(one["scored"]["kept"]) for one in own)
    asked = sum(len(one["metrics"]) for one in own)
    explained = sum(one["scored"]["explained"] for one in own)
    return (f"{model:14} {KINDS[one_metric]:12} calls {len(own)}  explained {explained}  "
            f"kept {kept} of {asked}  drops {dict(sorted(drops.items()))}")


def summary(path: Path) -> str:
    """Score every recorded call by replay, and give the summary's text."""
    _, calls = recorded_calls(path)
    findings = {one.key: one.finding for one in read_dataset(DATASET)}
    scored = [one | {"scored": replayed(one, findings)} for one in calls]
    differing = [f"{one['model']} seed {one['seed']} {one['advisory_id']}"
                 for one in scored if one["scored"] != one["outcome"]]
    models = sorted({one["model"] for one in scored})
    code = ", ".join(f"{name} {blob_id(module)}" for name, module in SCORING_CODE.items())
    return "\n".join([
        f"scored by {code}",
        f"calls {len(scored)}; scored otherwise than recorded at the time: {len(differing)}",
        *differing, "", *map(row, scored), "",
        *(tally(model, kind, scored) for model, kind in product(models, KINDS)),
    ]) + "\n"


def scored_block(text: str) -> str:
    """Give what the README shows of a summary: its scoring and its counts, not its rows."""
    sections = text.split(SECTION)
    if len(sections) != 3:
        raise ValueError(f"a summary has scoring, rows and counts; this has {len(sections)} parts")
    scoring, _, counts = sections
    return scoring + SECTION + counts


def with_block(readme: str, block: str) -> str:
    """Give the README with its scored block replaced, refusing one without one pair of markers."""
    if readme.count(BLOCK_BEGIN) != 1 or readme.count(BLOCK_END) != 1:
        raise ValueError("the README must hold each scored-block marker exactly once")
    before, rest = readme.split(BLOCK_BEGIN)
    _, after = rest.split(BLOCK_END)
    return before + BLOCK_BEGIN + block + BLOCK_END + after


def write_record(folder: Path) -> None:
    """Re-score a record's replies into its summary and its README's block, both or neither."""
    text = summary(folder / REPLIES)
    readme = with_block((folder / README).read_text(encoding="utf-8"), scored_block(text))
    (folder / SUMMARY).write_text(text, encoding="utf-8")
    (folder / README).write_text(readme, encoding="utf-8")


def main(argv: list[str]) -> int:
    """Print the summary of the replies named, or rewrite this record's summary and README."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("replies", nargs="?", type=Path, help="print the summary of these replies")
    parser.add_argument("--write", action="store_true", help=WRITE_HELP)
    options = parser.parse_args(argv)
    if options.write == (options.replies is not None):
        parser.error("give a replies file to print its summary, or --write, and not both")
    if options.write:
        write_record(RECORD)
        return 0
    sys.stdout.write(summary(options.replies))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
