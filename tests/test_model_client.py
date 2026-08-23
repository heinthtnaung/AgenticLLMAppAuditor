"""The local model client answers from a running server and fails clearly without one.

The success-path test is skipped when no Ollama server is listening, so the
suite still runs on a machine that has not set one up. It is never faked: a
mocked reply would claim Task 1.2 works without ever proving it.
"""

import json
import socket
import urllib.parse
import urllib.request

import pytest

import config
import model_client


def unused_local_url() -> str:
    """Return a localhost URL on a port nothing is listening on."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    return f"http://127.0.0.1:{port}/api/generate"


@pytest.mark.parametrize("prompt", ["", "   ", "\n\t"])
def test_empty_prompt_is_rejected(prompt: str) -> None:
    """An empty or whitespace-only prompt fails before any request is made."""
    with pytest.raises(ValueError, match="prompt must not be empty"):
        model_client.ask(prompt)


def test_unreachable_server_names_the_url(monkeypatch) -> None:
    """When nothing is listening, the error names the server URL the client tried."""
    url = unused_local_url()
    monkeypatch.setattr(model_client, "SERVER_URL", url)
    with pytest.raises(RuntimeError, match="cannot reach the local model server") as error:
        model_client.ask("say hello")
    assert url in str(error.value)


def test_unreachable_server_says_how_to_start_it(monkeypatch) -> None:
    """The error tells the reader how to start the server and pull the model."""
    monkeypatch.setattr(model_client, "SERVER_URL", unused_local_url())
    with pytest.raises(RuntimeError) as error:
        model_client.ask("say hello")
    assert "ollama serve" in str(error.value)
    assert model_client.MODEL in str(error.value)


def local_server_is_running() -> bool:
    """Say whether an Ollama server is answering. Any connection problem counts as no."""
    try:
        host = urllib.parse.urlparse(model_client.SERVER_URL)
        with socket.socket() as probe:
            probe.settimeout(1)
            return probe.connect_ex((host.hostname, host.port or 80)) == 0
    except OSError:
        # An unresolvable or malformed host is simply not a running server.
        return False


def configured_model_is_available() -> bool:
    """Say whether the server has actually pulled the model the settings ask for."""
    tags_url = model_client.SERVER_URL.replace("/api/generate", "/api/tags")
    try:
        with urllib.request.urlopen(tags_url, timeout=5) as response:
            pulled = {model["name"] for model in json.loads(response.read()).get("models", [])}
    except (OSError, ValueError):
        return False
    return model_client.MODEL in pulled


def test_ask_returns_text_from_the_local_server() -> None:
    """Task 1.2's done-criterion: a real prompt gets a real reply, with no internet."""
    if not local_server_is_running():
        pytest.skip("no local Ollama server running")
    if not configured_model_is_available():
        pytest.skip(f"model {model_client.MODEL} is not pulled on the local server")
    reply = model_client.ask("Reply with the single word: hello")
    assert isinstance(reply, str)
    assert reply.strip()


def test_server_probe_survives_an_unresolvable_host(monkeypatch) -> None:
    """A mistyped AUDITOR_SERVER_URL must not break collection of the whole suite."""
    monkeypatch.setattr(model_client, "SERVER_URL", "http://no-such-host.invalid:11434/api/generate")
    assert local_server_is_running() is False


def test_settings_come_from_config_not_hardcoded() -> None:
    """The whole point of src/config.py: model_client mirrors whatever config resolves."""
    assert model_client.MODEL == config.get("AUDITOR_MODEL")
    assert model_client.SERVER_URL == config.get("AUDITOR_SERVER_URL")
    assert model_client.TIMEOUT_SECONDS == config.get_int("AUDITOR_TIMEOUT_SECONDS")
    assert isinstance(model_client.TIMEOUT_SECONDS, int)
