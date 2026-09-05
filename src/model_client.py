"""Thin client for the local Ollama model server.

Set up in Phase 1 and used from Phase 3 by `checks/advise.py`, which asks it
how to fix each finding, and from Phase 6 by `retrieval/retrieve.py`, which
asks it to embed text so the knowledge base can be searched. No detection logic
uses it: what it writes lands in `remediation.json`, never in a scored artifact.
Uses urllib rather than the ollama package to keep the stdlib-first rule, and
it is the one module in `src/` that opens a network connection -- a test holds
that by name, so the two callers share this file rather than each opening one.
The settings come from the environment, so no machine-specific value is baked
into the source. See .env.example. They are read once at import, so editing
.env takes effect on the next run, not mid-run.
"""

import json
import urllib.error
import urllib.request

import config

# What the model is asked to do here is explain evidence this project already
# gathered, so a sampled answer is noise rather than variety. Greedy decoding
# with a fixed seed is what lets findings.json record settings a later run can
# repeat -- without these, "reproducible prose" is a claim with nothing behind
# it. Recorded verbatim in the artifact's model_run block.
DECODE_SETTINGS = {"temperature": 0, "seed": 0}

MODEL = config.get("AUDITOR_MODEL")
EMBED_MODEL = config.get("AUDITOR_EMBED_MODEL")
SERVER_URL = config.get("AUDITOR_SERVER_URL")
TIMEOUT_SECONDS = config.get_int("AUDITOR_TIMEOUT_SECONDS")

# Ollama answers 404 for a model it has not pulled. Its own message is the
# fix: a reader should pull the model, not restart the server.
MODEL_MISSING_STATUS = 404

if TIMEOUT_SECONDS <= 0:
    raise ValueError(f"AUDITOR_TIMEOUT_SECONDS must be greater than zero, got {TIMEOUT_SECONDS}")


class ModelNotPulled(RuntimeError):
    """The server answered, but has no model of that name.

    A `RuntimeError` still, so every caller that degrades on an unreachable
    server degrades on this too; the subclass lets one that cares record the
    more useful reason.
    """


def _endpoint(name: str) -> str:
    """Another route on the same server, so one URL setting covers them all."""
    return SERVER_URL.rsplit("/", 1)[0] + "/" + name


def _post(url: str, payload: dict, model: str) -> dict:
    """Send one JSON request to the local server and return its JSON reply."""
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        if error.code == MODEL_MISSING_STATUS:
            raise ModelNotPulled(
                f"model server at {url} has no model {model!r}. Pull it with "
                f"'ollama pull {model}'.") from error
        raise RuntimeError(
            f"model server at {url} returned HTTP {error.code}: {error.reason}"
        ) from error
    except OSError as error:
        # URLError and TimeoutError are both OSError subclasses.
        raise RuntimeError(
            f"cannot reach the local model server at {url}: {error}. "
            "Start it with 'ollama serve' and pull the model with "
            f"'ollama pull {model}'."
        ) from error
    except json.JSONDecodeError as error:
        raise RuntimeError(f"model server at {url} sent invalid json: {error}") from error


def ask(prompt: str, model: str = MODEL) -> str:
    """Send one prompt to the local model server and return its text reply.

    `model` defaults to the audit model; a caller that wants a different local
    model (the AI-formatted report uses gemma) passes it, and the rest of the
    offline, fixed-decode contract is unchanged.
    """
    if not prompt.strip():
        raise ValueError("prompt must not be empty")
    body = _post(SERVER_URL, {
        "model": model, "prompt": prompt, "stream": False, "options": DECODE_SETTINGS,
    }, model)
    if "response" not in body:
        raise RuntimeError(f"model server reply had no 'response' field: {body}")
    return body["response"]


def embed(texts: list[str], model: str = EMBED_MODEL) -> list[list[float]]:
    """Return one embedding vector per text, from the local embedding model.

    Deterministic for a given model: embeddings involve no sampling, so the
    same text yields the same vector and an index can be rebuilt bit for bit.
    """
    if not texts or any(not text.strip() for text in texts):
        raise ValueError("every text to embed must be non-empty")
    body = _post(_endpoint("embed"), {"model": model, "input": texts}, model)
    vectors = body.get("embeddings")
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        raise RuntimeError(
            f"model server returned {len(vectors) if isinstance(vectors, list) else 'no'} "
            f"embeddings for {len(texts)} texts")
    return vectors


def model_digest(model: str = MODEL) -> str | None:
    """Return the model's content digest, so a mutable tag is not the only record.

    One of the models compared is literally `:latest`, so a run recorded by tag
    alone is repeatable only until someone re-pulls. Read from the server's tag
    listing, which is where Ollama reports it -- `/api/show` does not. Still
    localhost, still offline. None when the model is not listed, rather than an
    error: an unrecorded digest is honest, a wrong one is not.
    """
    listing_url = _endpoint("tags")
    try:
        with urllib.request.urlopen(listing_url, timeout=TIMEOUT_SECONDS) as response:
            body = json.loads(response.read())
    except (urllib.error.HTTPError, OSError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"cannot reach the local model server at {listing_url}: {error}") from error
    for listed in body.get("models", []):
        if listed.get("name") == model:
            return listed.get("digest")
    return None


if __name__ == "__main__":
    # Task 1.2 smoke test: python src/model_client.py
    print(ask("Say hello in one short sentence."))
