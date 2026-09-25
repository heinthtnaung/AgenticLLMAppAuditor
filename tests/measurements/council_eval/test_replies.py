"""Guards on saved calls and their replay: the recorded answer, only to the recorded question."""

import json

import pytest

import eval_samples as samples
from cli.council_run import OLLAMA_PROVIDER, assess_one, build_roster
from council.prompt import build_prompt
from council.roster import Member
from council.transport import ModelUnavailable
from council_eval.recording import CallRecord, RecordingClient
from council_eval.replies import (
    ReplayClient,
    ReplayMismatch,
    call_line,
    read_replies,
)
from council_eval.variants import BASELINE, VARIANTS, Variant

MEMBER = Member(samples.MODEL, "ollama", samples.MODEL, "small", runs_local=True)
PROMPT = build_prompt("AV", samples.ADVISORY_TEXT)


def recorded_calls(variant: Variant = BASELINE) -> dict:
    """Record one member's eight calls on the sample item, the way a pass records them."""
    client = RecordingClient(post=samples.FakeServer(), clock=lambda: 0.0, variant=variant)
    assess_one(samples.finding(), build_roster((samples.MODEL,)), {OLLAMA_PROVIDER: client})
    return {(samples.KEY, samples.MODEL, one.metric): one for one in client.calls}


def written(path, lines) -> None:
    """Write lines of a replies file."""
    path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")


def test_a_replies_file_reads_back_every_call_it_holds(tmp_path):
    calls = recorded_calls()
    path = tmp_path / "pass.jsonl"
    header = samples.header()
    written(path, [header, *[call_line(key, model, one) for (key, model, _), one in calls.items()]])
    replies = read_replies((path,))
    assert replies.headers == (header,)
    assert replies.calls == calls


def test_a_file_without_its_header_is_refused(tmp_path):
    path = tmp_path / "pass.jsonl"
    written(path, [])
    with pytest.raises(ValueError, match="carry 0 headers"):
        read_replies((path,))


def test_two_passes_that_recorded_the_same_call_are_refused(tmp_path):
    line = call_line(samples.KEY, samples.MODEL, CallRecord("AV", "digest", None, 0.0))
    first, second = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    written(first, [{"kind": "header"}, line])
    written(second, [{"kind": "header"}, line])
    with pytest.raises(ValueError, match="recorded more than once"):
        read_replies((first, second))


def test_the_replay_answers_what_the_member_said():
    client = ReplayClient(samples.KEY, recorded_calls(), BASELINE, samples.WINDOW)
    assert client(MEMBER, PROMPT) == samples.ANSWERS["AV"]


def test_a_reply_recorded_for_another_request_is_refused():
    calls = recorded_calls()
    calls[(samples.KEY, samples.MODEL, "AV")] = CallRecord("AV", "another", {}, 0.0)
    with pytest.raises(ReplayMismatch, match="was asked otherwise"):
        ReplayClient(samples.KEY, calls, BASELINE, samples.WINDOW)(MEMBER, PROMPT)


def test_a_call_nobody_recorded_is_refused():
    with pytest.raises(ReplayMismatch, match="was recorded"):
        ReplayClient(samples.KEY, {}, BASELINE, samples.WINDOW)(MEMBER, PROMPT)


def test_a_call_that_got_nothing_back_fails_again_as_the_member_s():
    calls = recorded_calls()
    sent = calls[(samples.KEY, samples.MODEL, "AV")].request_sha256
    calls[(samples.KEY, samples.MODEL, "AV")] = CallRecord("AV", sent, None, 0.0)
    with pytest.raises(ModelUnavailable, match="sent nothing back"):
        ReplayClient(samples.KEY, calls, BASELINE, samples.WINDOW)(MEMBER, PROMPT)


def test_a_recorded_answer_to_a_prompt_the_server_cut_fails_again_as_it_did_live():
    calls = recorded_calls()
    key = (samples.KEY, samples.MODEL, "AV")
    cut = calls[key].envelope | {"prompt_eval_count": 10}
    calls[key] = CallRecord("AV", calls[key].request_sha256, cut, 0.0)
    with pytest.raises(ModelUnavailable, match="read this AV prompt as 10 tokens"):
        ReplayClient(samples.KEY, calls, BASELINE, samples.WINDOW)(MEMBER, PROMPT)


def test_a_replay_fault_stops_the_product_s_runner_rather_than_passing_as_a_failed_member():
    # The runner records ModelUnavailable and ValueError as a member that failed.
    # A replay that has no answer must not be scored as a model that gave none.
    with pytest.raises(ReplayMismatch):
        assess_one(
            samples.finding(), build_roster((samples.MODEL,)),
            {OLLAMA_PROVIDER: ReplayClient(samples.KEY, {}, BASELINE, samples.WINDOW)},
        )


@pytest.mark.parametrize("variant", VARIANTS.values(), ids=VARIANTS)
def test_a_pass_replays_only_as_the_variant_it_was_asked_in(variant):
    calls = recorded_calls(variant)
    client = ReplayClient(samples.KEY, calls, variant, samples.WINDOW)
    assert client(MEMBER, PROMPT) == samples.ANSWERS["AV"]
    for other in (one for one in VARIANTS.values() if one != variant):
        with pytest.raises(ReplayMismatch, match="was asked otherwise"):
            ReplayClient(samples.KEY, calls, other, samples.WINDOW)(MEMBER, PROMPT)
