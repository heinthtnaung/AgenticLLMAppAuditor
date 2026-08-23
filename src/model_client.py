"""Thin client for the local Ollama model server.

Set up in Phase 1 so it is ready for Phase 3; no detection logic uses it yet.
Uses urllib rather than the ollama package to keep the stdlib-first rule.
The three settings come from the environment, so no machine-specific value
is baked into the source. See .env.example. They are read once at import, so
editing .env takes effect on the next run, not mid-run.
"""

import json
import urllib.error
import urllib.request

import config

MODEL = config.get("AUDITOR_MODEL")
SERVER_URL = config.get("AUDITOR_SERVER_URL")
TIMEOUT_SECONDS = config.get_int("AUDITOR_TIMEOUT_SECONDS")

if TIMEOUT_SECONDS <= 0:
    raise ValueError(f"AUDITOR_TIMEOUT_SECONDS must be greater than zero, got {TIMEOUT_SECONDS}")


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


if __name__ == "__main__":
    # Task 1.2 smoke test: python src/model_client.py
    print(ask("Say hello in one short sentence."))
