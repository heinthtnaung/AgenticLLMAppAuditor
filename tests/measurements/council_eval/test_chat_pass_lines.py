"""Guards on a pasted pass's lines: `collect`'s shape, the unknowns said, every reply kept whole."""

import json

import chat_samples
import eval_samples as samples
from council.prompt import PROMPT_VERSION
from council_eval.chat_pass_lines import pass_lines
from council_eval.chat_passes import answered_prompts
from council_eval.chat_reply import ChatReply
from council_eval.chat_reply_file import SavedReply, read_saved_reply
from council_eval.collect import write_line
from council_eval.replies import read_replies
from council_eval.variants import CHAT, CHAT_REVERSED
from cvss.metrics import METRIC_ORDER


def dated_reply(prompt_id: str, date: str) -> ChatReply:
    """Build a read reply to one prompt, pasted on a given day."""
    saved = SavedReply(f"{prompt_id}.txt", "m", date, "web", "the reply")
    return ChatReply(saved, prompt_id, chat_samples.READINGS)


def lines_of(variant=CHAT):
    """Give one order's pass over the fixtures."""
    return pass_lines(chat_samples.fixtures_answered(), variant, "d" * 64, chat_samples.no_git)


def test_the_header_records_the_model_as_typed_and_every_pinning_as_unknown():
    header = lines_of()[0]
    assert header["model"] == chat_samples.FIXTURE_MODEL
    assert header["interface"] == chat_samples.FIXTURE_INTERFACE
    assert header["prompt_version"] == CHAT.prompt_version
    assert [header[name] for name in ("temperature", "seed", "num_ctx", "think")] == ["unknown"] * 4
    assert header["provenance"] == "chat interface; weights, temperature and seed unknown"
    code = (header["dataset_sha256"], header["commit"], header["changes"])
    assert code == ("d" * 64, "abc123", [])


def test_the_header_says_the_prompt_is_not_the_council_s():
    assert f"not the local council's {PROMPT_VERSION}" in lines_of()[0]["prompt_shape"]


def test_web_browsing_is_recorded_as_not_checked():
    # A known gap, asserted so that closing it turns this red: nothing in a
    # pasted reply shows whether the chat searched the web.
    assert lines_of()[0]["web_browsing"].startswith("not checked")


def test_a_fresh_chat_per_prompt_is_recorded_as_the_procedure_and_not_checked():
    # A known gap, asserted so that closing it turns this red: a pasted reply
    # cannot show whether its chat had seen another prompt first.
    assert lines_of()[0]["turn_start"].endswith("not checked")


def test_the_dates_are_the_ones_the_person_wrote_in_that_order_s_replies():
    assert (lines_of()[0]["started"], lines_of()[0]["ended"]) == ("2026-10-01", "2026-10-01")
    assert lines_of(CHAT_REVERSED)[0]["started"] == "2026-10-02"


def test_a_pass_of_replies_pasted_on_several_days_runs_from_the_first_to_the_last():
    prompts = chat_samples.prompts(chat_samples.TWO_ITEMS)
    dates = ("2026-10-03", "2026-10-03", "2026-10-01", "2026-10-02")
    replies = tuple(dated_reply(one.prompt_id, date) for one, date in zip(prompts, dates))
    header = pass_lines(answered_prompts(prompts, replies), CHAT, "d" * 64, chat_samples.no_git)[0]
    assert (header["started"], header["ended"]) == ("2026-10-01", "2026-10-03")


def test_each_reply_is_kept_whole_beside_its_fingerprint_and_its_prompt_s():
    pasted = lines_of()[1]
    saved = read_saved_reply(chat_samples.FORWARD_FIXTURE)
    prompt = chat_samples.prompts()[0]
    assert (pasted["kind"], pasted["reply"], pasted["reply_sha256"]) == (
        "pasted", saved.reply, saved.sha256
    )
    assert (pasted["prompt_id"], pasted["prompt_sha256"]) == (prompt.prompt_id, prompt.sha256)


def test_each_metric_is_a_call_answering_the_prompt_pasted_with_its_three_fields():
    calls = [line for line in lines_of() if line["kind"] == "call"]
    assert [one["metric"] for one in calls] == list(METRIC_ORDER)
    first = calls[0]
    assert first["request_sha256"] == chat_samples.prompts()[0].sha256
    assert json.loads(first["envelope"]["response"])["evidence"] == samples.REMOTE
    assert first["seconds"] is None


def test_a_pass_reads_back_as_any_pass_does(tmp_path):
    path = tmp_path / "pass.jsonl"
    with path.open("x", encoding="utf-8") as written:
        for line in lines_of(CHAT_REVERSED):
            write_line(written, line)
    read = read_replies((path,))
    assert read.headers[0]["prompt_version"] == CHAT_REVERSED.prompt_version
    assert len(read.calls) == len(METRIC_ORDER)
