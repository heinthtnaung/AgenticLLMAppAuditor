"""Guards on replaying a pasted pass: the reply to the prompt pasted, and to nothing else."""

import json

import pytest

import chat_samples
import eval_samples as samples
from council.prompt import build_prompt
from council_eval.chat_replay import PastedReplayClient, chat_member
from council_eval.recording import CallRecord
from council_eval.replies import ReplayMismatch

MEMBER = chat_member(chat_samples.FIXTURE_MODEL)
PROMPT = build_prompt("UI", samples.ADVISORY_TEXT)
SAID = json.dumps(chat_samples.READINGS["UI"])


def calls(request_sha256: str) -> dict:
    """Record the sample item's UI as a pasted call answering one prompt."""
    record = CallRecord("UI", request_sha256, {"response": SAID}, None)
    return {(samples.KEY, MEMBER.model, "UI"): record}


def test_a_call_to_the_prompt_pasted_is_answered_as_the_reply_said():
    forward = chat_samples.prompts()[0]
    client = PastedReplayClient(samples.KEY, calls(forward.sha256), reversed_options=False)
    assert client(MEMBER, PROMPT) == SAID


def test_a_reply_to_the_other_order_s_prompt_is_refused():
    reversed_ = chat_samples.prompts()[1]
    client = PastedReplayClient(samples.KEY, calls(reversed_.sha256), reversed_options=False)
    with pytest.raises(ReplayMismatch, match="was asked otherwise"):
        client(MEMBER, PROMPT)


def test_a_metric_nobody_pasted_is_refused():
    client = PastedReplayClient(samples.KEY, {}, reversed_options=False)
    with pytest.raises(ReplayMismatch, match="no call of"):
        client(MEMBER, PROMPT)


def test_a_chat_member_is_hosted_and_its_text_left_the_machine():
    who = MEMBER.identify("v")
    assert (MEMBER.provider, MEMBER.runs_local, MEMBER.egress) == ("chat", False, True)
    assert who.ran_local is False
    assert MEMBER.model == MEMBER.name == chat_samples.FIXTURE_MODEL
