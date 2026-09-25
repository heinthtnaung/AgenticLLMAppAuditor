"""Guards on the order-checked step: every roster scored, with each member's verdicts beside it."""

import io

import eval_samples as samples
from council_eval import commands
from council_eval.collect import collect
from council_eval.dataset import write_dataset
from council_eval.order_checked_step import verdict_table
from council_eval.variants import REVERSED

REVERSED_ANSWERS = samples.ANSWERS | {"AV": samples.reply("L")}


def passes(tmp_path) -> tuple:
    """Freeze the sample item and take one pass of the sample model in each order."""
    dataset = tmp_path / "dataset.json"
    write_dataset((samples.item(),), {"repository": "example"}, dataset)
    forward, reversed_ = tmp_path / "forward.jsonl", tmp_path / "reversed.jsonl"
    item = (samples.item(),)
    collect(item, samples.MODEL, forward, samples.header(), samples.Asking(), io.StringIO())
    asked = samples.Asking(REVERSED_ANSWERS, REVERSED)
    collect(item, samples.MODEL, reversed_, samples.header(variant=REVERSED), asked, io.StringIO())
    return dataset, forward, reversed_


def test_the_step_scores_each_roster_order_checked_with_its_verdicts(tmp_path, capsys):
    dataset, forward, reversed_ = passes(tmp_path)
    commands.main(
        ["order-checked", "--dataset", str(dataset), "--forward", str(forward),
         "--reversed", str(reversed_)]
    )
    out = capsys.readouterr().out.splitlines()
    assert f"ROSTER {samples.MODEL}, order-checked  (1 items)" in out
    rows = [line.split() for line in out if line.startswith(samples.MODEL)]
    assert [samples.MODEL, "AV", "0", "1", "0", "0"] in rows
    assert [samples.MODEL, "UI", "1", "0", "0", "0"] in rows


def test_a_verdict_table_counts_each_member_s_metrics_and_names_every_one():
    verdicts = [("k1", "a:1b", "AV", "stable"), ("k2", "a:1b", "AV", "order-sensitive")]
    lines = verdict_table(verdicts, ("a:1b",))
    columns = ["member", "metric", "stable", "order-sensitive", "declined", "failed"]
    assert lines[0].split() == columns
    assert lines[1].split() == ["a:1b", "AV", "1", "1", "0", "0"]
    assert len(lines) == 1 + 8
