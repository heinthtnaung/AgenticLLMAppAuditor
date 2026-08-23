"""The local model client validates its input and fails clearly when the server is down.

Ollama is not installed in this environment, so there is no success-path test here.
Faking a successful reply would claim a task (Phase 1, task 1.2) that is not finished.
"""

import socket

import pytest
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
