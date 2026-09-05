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
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config import ENV_FILE, read_env_file  # noqa: E402

API_URL = "https://openrouter.ai/api/v1/chat/completions"
KEY_VARIABLE = "OPENROUTER_API_KEY"
MODEL_VARIABLE = "OPENROUTER_MODEL"

# Used when neither the environment, `.env`, nor --cloud-model names one.
FALLBACK_MODEL = "z-ai/glm-5.2"

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


def api_key(env_file: Path = ENV_FILE) -> str:
    """The key, from the environment or `.env`, refusing by name and never by value.

    A real environment variable wins, the way `config` treats every other
    setting. `.env` is gitignored, so a key there is not a key in the repository
    -- but it is a key on disk, which an exported shell variable is not.

    Deliberately not routed through `config.get`: that validates against
    `DEFAULTS` and would have to learn a cloud setting, which belongs to the
    study and not to the auditor. `config` ignores any name without the
    `AUDITOR_` prefix, so this one passes through its checks untouched.
    """
    key = os.environ.get(KEY_VARIABLE, "").strip()
    if not key and env_file.is_file():
        key = read_env_file(env_file).get(KEY_VARIABLE, "").strip()
    if not key:
        raise RuntimeError(
            f"{KEY_VARIABLE} is set neither in the environment nor in {env_file.name}. "
            "It is needed only by the local-versus-hosted study, never by an audit.")
    return key


def default_model(env_file: Path = ENV_FILE) -> str:
    """The hosted model to use when none is named on the command line.

    Same precedence as the key: a real environment variable, then `.env`,
    then a fallback -- so a study can be re-run with one setting changed and
    no code edited.
    """
    named = os.environ.get(MODEL_VARIABLE, "").strip()
    if not named and env_file.is_file():
        named = read_env_file(env_file).get(MODEL_VARIABLE, "").strip()
    return named or FALLBACK_MODEL


def ask(prompt: str, model: str | None = None, post_fn=None, timeout: int = 180) -> str:
    """Ask the hosted model one question and return its text.

    Same contract as `model_client.ask`: text out, `RuntimeError` on any failure,
    so every degradation path already built for the local model works unchanged.
    `post_fn` is injected so a test can drive this without a socket or a key.
    """
    model = model or default_model()
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
