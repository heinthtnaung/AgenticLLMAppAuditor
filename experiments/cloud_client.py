"""Asks a hosted model, for the local-vs-cloud study only.

**Outside `src/` on purpose.** The auditor's published guarantee is that its
audit path opens no socket except to local Ollama, and
`tests/parsing/test_offline_containment.py` asserts an *exact* set of modules
that reach the network. This module would break that set. It is not part of the
tool: it is part of the study that evaluates the tool, and nothing under `src/`
may import it -- which the same test now enforces in both directions.

The key is read from the environment and never written anywhere. Error messages
name the variable, never its value, and never echo headers or the request body.
"""

import json
import os
import urllib.error
import urllib.request

API_URL = "https://openrouter.ai/api/v1/chat/completions"
KEY_VARIABLE = "OPENROUTER_API_KEY"
DEFAULT_MODEL = "z-ai/glm-5.2"

# Generous, because GLM-5.2 is a reasoning model: it spends tokens on a
# `reasoning` field first and returns `content: null` if the budget runs out
# before it starts answering. Measured: 1200 was too small for the planner
# prompt, which describes every surface. A null content is a failed answer,
# never an empty
# verdict -- reading it as "the model said nothing conclusive" would put a
# claim in an artifact that nothing supports.
MAX_TOKENS = 4000

# Matching the local client's decode settings, so the two arms differ by model
# and not by sampling. The cloud side still has no `seed` equivalent.
DECODE_SETTINGS = {"temperature": 0, "max_tokens": MAX_TOKENS}


def _post(payload: dict, key: str, timeout: int) -> dict:
    """Send one request. Raises `RuntimeError` for anything but a usable reply."""
    request = urllib.request.Request(
        API_URL, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        # The status and reason only. The body may echo the request, and the
        # request carries the audited app's source.
        raise RuntimeError(f"{API_URL} returned HTTP {error.code}: {error.reason}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot reach {API_URL}: {error}") from error


def api_key() -> str:
    """The key from the environment, or a refusal naming the variable and not its value."""
    key = os.environ.get(KEY_VARIABLE, "").strip()
    if not key:
        raise RuntimeError(
            f"{KEY_VARIABLE} is not set. Export it for this shell only; it must not "
            "be written to .env, an artifact, or a commit.")
    return key


def ask(prompt: str, model: str = DEFAULT_MODEL, post_fn=None, timeout: int = 180) -> str:
    """Ask the hosted model one question and return its text.

    Same contract as `model_client.ask`: text out, `RuntimeError` on any failure,
    so every degradation path already built for the local model works unchanged.
    `post_fn` is injected so a test can drive this without a socket or a key.
    """
    send = post_fn or (lambda payload: _post(payload, api_key(), timeout))
    body = send({"model": model, "temperature": 0, "max_tokens": MAX_TOKENS,
                 "messages": [{"role": "user", "content": prompt}]})
    choices = body.get("choices") or []
    content = choices[0].get("message", {}).get("content") if choices else None
    if not content:
        raise RuntimeError(
            f"{model} returned no content; a reasoning model can spend the whole "
            f"{MAX_TOKENS}-token budget before answering")
    return content
