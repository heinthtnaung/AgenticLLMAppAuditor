"""Guards on one pass: each item from a fresh load, eight calls, and every call on its own line."""

import io
import json
import re

import pytest

import eval_samples as samples
from cli.council_run import assess_one, build_roster
from council.prompt import REVERSED_PROMPT_VERSION
from council.roster import OLLAMA_PROVIDER
from council_eval import collect as collect_module
from council_eval.collect import ask_item, collect, first_load_seconds, progress_line
from council_eval.recording import CallRecord, RecordingClient
from council_eval.variants import LIBRARY_GUIDANCE, LIBRARY_REVERSED, VariantMismatch
from cvss.metrics import METRIC_ORDER

HEADER = samples.header()


def test_an_item_is_asked_from_a_fresh_load():
    server = samples.FakeServer()
    ask_item(samples.item(), samples.MODEL, server)
    assert server.posted[0] == {"model": samples.MODEL, "keep_alive": 0}


def test_an_item_is_asked_every_metric_in_the_product_s_order():
    server = samples.FakeServer()
    records = ask_item(samples.item(), samples.MODEL, server)
    assert [one.metric for one in records] == list(METRIC_ORDER)
    assert [samples.metric_of(one) for one in server.posted[1:]] == list(METRIC_ORDER)


def test_a_pass_asked_with_the_audit_s_order_check_on_stops_rather_than_record_it():
    # The recording client words only the product's in-order prompt, so the
    # pass is asked with the check off (`variants.PASS_ORDER_CHECK`).
    client = RecordingClient(post=samples.FakeServer(), clock=lambda: 0.0)
    roster, clients = build_roster((samples.MODEL,)), {OLLAMA_PROVIDER: client}
    with pytest.raises(VariantMismatch, match=re.escape(REVERSED_PROMPT_VERSION)):
        assess_one(samples.finding(), roster, clients)


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


def test_an_item_asked_in_a_variant_s_words_is_sent_them_on_every_metric():
    server = samples.FakeServer()
    ask_item(samples.item(), samples.MODEL, server, LIBRARY_REVERSED)
    assert all(LIBRARY_GUIDANCE in payload["system"] for payload in server.posted[1:])
    assert len(server.posted[1:]) == len(METRIC_ORDER)


def test_an_item_is_asked_naming_no_escalation_model_rather_than_leaving_it_to_a_default(
    monkeypatch,
):
    # A pass holds one model's calls: an escalation would ask a model it never recorded.
    options = []
    monkeypatch.setattr(
        collect_module, "assess_one", lambda *given, **named: options.append(named)
    )
    ask_item(samples.item(), samples.MODEL, samples.FakeServer())
    assert options == [{"order_check": False, "escalation": None}]
