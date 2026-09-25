"""Guards on counting a prompt's tokens: the product's request, any model, one token generated."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "measurements"))

import prompt_tokens  # noqa: E402
from council.ollama import LocalModel, build_request  # noqa: E402
from council.prompt import build_prompt  # noqa: E402

PROMPT = build_prompt("AC", "A flaw was found.")


class Counting:
    """A stand-in for Ollama that counts every prompt at a fixed number of tokens."""

    def __init__(self, tokens: int) -> None:
        """Hold the count to report, and remember every request."""
        self.tokens = tokens
        self.posted: list[dict] = []

    def __call__(self, url: str, payload: dict) -> dict:
        """Answer with the count, as Ollama's envelope carries it."""
        self.posted.append(payload)
        return {"prompt_eval_count": self.tokens}


def test_a_prompt_is_counted_as_a_member_sends_it_in_a_window_nothing_is_cut_from():
    server = Counting(430)
    assert prompt_tokens.count_tokens(PROMPT, "other:7b", server) == 430
    expected = build_request(PROMPT, LocalModel(model="other:7b", context_tokens=32_768))
    expected["options"]["num_predict"] = 1
    assert server.posted == [expected]


def test_a_model_that_reports_no_count_is_refused():
    with pytest.raises(ValueError, match="returned no prompt_eval_count"):
        prompt_tokens.count_tokens(PROMPT, "other:7b", lambda url, payload: {})


def test_the_estimate_s_error_and_what_the_guard_s_limit_would_cost_are_printed():
    lines = prompt_tokens.model_lines("other:7b", PROMPT, PROMPT, Counting(430))
    estimated = prompt_tokens.estimated_tokens(PROMPT)
    assert f"off by {430 - estimated:+d}" in lines[2]
    assert lines[3].endswith(f"about {round(8192 * 0.75 * 430 / estimated)} of the 8192 pinned")


def serving(url: str) -> dict:
    """Answer the two reads that name the server and the weights."""
    if url.endswith("/api/version"):
        return {"version": "0.34.3"}
    names = ("a:1b", "b:2b", "qwen2.5:7b-instruct")
    return {"models": [{"name": name, "digest": f"sha-{name}"} for name in names]}


def test_every_model_named_is_counted_by_its_weights_and_the_pinned_one_when_none_is(
    monkeypatch, capsys
):
    monkeypatch.setattr(prompt_tokens, "longest_advisory", lambda: ("GHSA-x", "A flaw."))
    prompt_tokens.main(["a:1b", "b:2b"], Counting(430), serving)
    prompt_tokens.main([], Counting(430), serving)
    named = [line for line in capsys.readouterr().out.splitlines() if not line.startswith(" ")]
    heading = [
        "prompt member-base-metric-3, Ollama 0.34.3", "the longest advisory, GHSA-x: 7 characters",
    ]
    assert named == [*heading, "a:1b sha-a:1b", "b:2b sha-b:2b",
                     *heading, "qwen2.5:7b-instruct sha-qwen2.5:7b-instruct"]


def test_a_model_the_server_does_not_hold_is_refused_before_it_is_counted(monkeypatch):
    monkeypatch.setattr(prompt_tokens, "longest_advisory", lambda: ("GHSA-x", "A flaw."))
    with pytest.raises(ValueError, match="the server holds no c:3b"):
        prompt_tokens.main(["c:3b"], Counting(430), serving)
