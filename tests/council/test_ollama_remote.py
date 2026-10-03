"""Guards on an Ollama member's host: this machine, or the one server elsewhere opted in to."""

import pytest

import council.ollama
from council.ollama import GENERATE_PATH, LocalModel, ask, generate_url
from council.prompt import build_prompt
from council.settings import Settings
from council_samples import ADVISORY

PROMPT = build_prompt("AV", ADVISORY)
# Another documentation address (RFC 5737), and not the one the settings name.
OTHER_MACHINE = "http://198.51.100.7:11434"
REPLY = {"model": "qwen2.5:7b-instruct", "response": '{"value": "N"}', "done_reason": "stop"}


def test_without_the_key_a_host_elsewhere_is_refused_naming_the_key():
    with pytest.raises(ValueError, match=r"is not this machine.*AUDITOR_REMOTE_SERVER=yes"):
        LocalModel(host=OTHER_MACHINE)


def test_with_the_key_a_member_named_no_further_is_asked_on_the_server_elsewhere(remote_server):
    sent = []

    def transport(url, payload):
        """Note where the call went, and answer as Ollama does."""
        sent.append(url)
        return REPLY

    pinning = LocalModel()
    assert pinning.host == remote_server
    assert ask(PROMPT, pinning, transport).text == REPLY["response"]
    assert sent == [f"{remote_server}{GENERATE_PATH}"]


def test_with_the_key_only_the_server_the_settings_name_is_allowed(remote_server):
    with pytest.raises(ValueError, match="is not this machine"):
        LocalModel(host=OTHER_MACHINE)


def test_with_the_key_this_machine_is_still_a_host_a_member_may_use(remote_server):
    assert generate_url(LocalModel(host="http://127.0.0.1:11434")).endswith(GENERATE_PATH)


def test_a_host_elsewhere_is_refused_where_the_key_names_this_machine(monkeypatch):
    # Opted in, but the settings' server is loopback: nothing elsewhere was chosen.
    here = Settings("qwen2.5:7b-instruct", "http://127.0.0.1:11434", 180.0, 8192, True)
    monkeypatch.setattr(council.ollama, "current_settings", lambda: here)
    with pytest.raises(ValueError, match="is not this machine"):
        LocalModel(host=OTHER_MACHINE)


def test_a_server_elsewhere_named_without_the_opt_in_is_refused_all_the_same(monkeypatch):
    # `load_settings` never builds such settings; were one built, no member would use it.
    unopted = Settings("qwen2.5:7b-instruct", "http://192.0.2.15:11434", 180.0, 8192)
    monkeypatch.setattr(council.ollama, "current_settings", lambda: unopted)
    with pytest.raises(ValueError, match="is not this machine"):
        LocalModel()
