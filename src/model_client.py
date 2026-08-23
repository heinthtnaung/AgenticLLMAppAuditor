"""Thin client for the local Ollama model server.

Set up in Phase 1 so it is ready for Phase 3; no detection logic uses it yet.
Uses urllib rather than the ollama package to keep the stdlib-first rule.
"""

import json
import urllib.error
import urllib.request

MODEL = "qwen2.5-coder:7b-instruct"
SERVER_URL = "http://localhost:11434/api/generate"
TIMEOUT_SECONDS = 120


def ask(prompt: str) -> str:
    """Send one prompt to the local model server and return its text reply."""
    if not prompt.strip():
        raise ValueError("prompt must not be empty")

    payload = json.dumps({"model": MODEL, "prompt": prompt, "stream": False}).encode()
    request = urllib.request.Request(
        SERVER_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"model server at {SERVER_URL} returned HTTP {error.code}: {error.reason}"
        ) from error
    except OSError as error:
        # URLError and TimeoutError are both OSError subclasses.
        raise RuntimeError(
            f"cannot reach the local model server at {SERVER_URL}: {error}. "
            "Start it with 'ollama serve' and pull the model with "
            f"'ollama pull {MODEL}'."
        ) from error
    except json.JSONDecodeError as error:
        raise RuntimeError(f"model server at {SERVER_URL} sent invalid json: {error}") from error

    if "response" not in body:
        raise RuntimeError(f"model server reply had no 'response' field: {body}")
    return body["response"]
