"""Guards on one pass: each item from a fresh load, eight calls, and every call on its own line."""

import io
import json

import pytest

import eval_samples as samples
from cvss.metrics import METRIC_ORDER
from council_eval.collect import ask_item, collect, first_load_seconds, progress_line
from council_eval.recording import CallRecord

HEADER = {"kind": "header", "model": samples.MODEL}


def test_an_item_is_asked_from_a_fresh_load():
    server = samples.FakeServer()
    ask_item(samples.item(), samples.MODEL, server)
    assert server.posted[0] == {"model": samples.MODEL, "keep_alive": 0}


def test_an_item_is_asked_every_metric_in_the_product_s_order():
    server = samples.FakeServer()
    records = ask_item(samples.item(), samples.MODEL, server)
    assert [one.metric for one in records] == list(METRIC_ORDER)
    assert [samples.metric_of(one) for one in server.posted[1:]] == list(METRIC_ORDER)


def test_a_pass_writes_its_header_then_a_line_per_call_then_its_end(tmp_path):
    out = tmp_path / "pass.jsonl"
    calls = collect((samples.item(),), samples.MODEL, out, HEADER, samples.Asking(), io.StringIO())
    kinds = [json.loads(line)["kind"] for line in out.read_text().splitlines()]
    assert calls == 8
    assert kinds == ["header", *["call"] * 8, "end"]


def test_a_pass_never_overwrites_one_already_taken(tmp_path):
    out = tmp_path / "pass.jsonl"
    out.write_text("taken\n")
    with pytest.raises(FileExistsError):
        collect((samples.item(),), samples.MODEL, out, HEADER, samples.Asking(), io.StringIO())


def test_the_progress_line_says_how_long_the_model_took_to_load():
    records = [CallRecord("AV", "x", {"load_duration": 3_500_000_000}, 4.0)]
    line = progress_line(1, 18, samples.KEY, samples.MODEL, records)
    assert line.endswith("1 calls  4.0 s  first load 3.5 s")


def test_an_item_whose_first_call_got_nothing_back_shows_no_load():
    assert first_load_seconds([CallRecord("AV", "x", None, 1.0)]) == 0.0
