"""Guards on where an Ollama member is recorded as running: where its server is, and only there."""

from types import SimpleNamespace

import pytest

from council.prompt import build_prompt
from council.providers import ask_local_model, ollama_member, refuse_mislabelled
from council_samples import member

PROMPT = build_prompt("AV", "Some advisory text.")


def asking_nobody(prompt, pinning):
    """Fail the test: a mislabelled member must be refused before anything is sent."""
    raise AssertionError(f"{pinning.model} was asked on {pinning.host}")


def test_on_this_machine_a_member_runs_local_and_needs_no_egress():
    made = ollama_member("qwen2.5:7b")
    assert (made.provider, made.family, made.runs_local, made.egress) == (
        "ollama", "qwen2.5", True, False,
    )


def test_on_a_server_elsewhere_a_member_is_not_local_and_its_egress_is_the_opt_in(remote_server):
    made = ollama_member("qwen2.5:7b")
    assert (made.runs_local, made.egress, made.may_run(), made.is_hosted()) == (
        False, True, True, False,
    )
    assert made.identify("member-base-metric-3").ran_local is False


def test_a_member_on_the_server_elsewhere_is_asked_there(remote_server, monkeypatch):
    seen = {}

    def remember(prompt, pinning):
        """Keep the host the call was pinned to, and reply as a server would."""
        seen["host"] = pinning.host
        return SimpleNamespace(text="it said this")

    monkeypatch.setattr("council.providers.ask", remember)
    assert ask_local_model(ollama_member("qwen2.5:7b"), PROMPT) == "it said this"
    assert seen["host"] == remote_server


def test_a_member_recorded_local_is_not_asked_on_a_server_elsewhere(remote_server, monkeypatch):
    monkeypatch.setattr("council.providers.ask", asking_nobody)
    with pytest.raises(ValueError, match="recorded as run on this machine, but its server is"):
        ask_local_model(member(model="qwen2.5:7b", runs_local=True), PROMPT)


def test_a_member_recorded_elsewhere_is_not_asked_on_this_machine(monkeypatch):
    monkeypatch.setattr("council.providers.ask", asking_nobody)
    elsewhere = member(model="qwen2.5:7b", runs_local=False, egress=True)
    with pytest.raises(ValueError, match="recorded as run on another machine"):
        ask_local_model(elsewhere, PROMPT)


def test_a_member_recorded_where_its_server_is_passes():
    refuse_mislabelled(member(runs_local=True), "http://localhost:11434")
    refuse_mislabelled(member(runs_local=False, egress=True), "http://192.0.2.15:11434")
