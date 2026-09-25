"""What produced a pass, written as its first line before any model is asked.

Every figure scored from a pass carries this beside it: which weights answered
(the digest the server reports, not the tag), which server, the pinning the
product actually sends, the prompt version, the dataset's fingerprint, and the
code -- the commit and whatever in `src/` and `measurements/` was not committed.
A figure nobody can re-derive is not a measurement. The prompt version is the
variant's, which begins with the product's version it was made from.

The pinning is read from the product's own constants and `LocalModel`, never
restated here, so a pass cannot claim a seed or a temperature the request did
not carry.
"""

import hashlib
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from council.ollama import PINNED_TEMPERATURE, PINNED_THINKING, LocalModel
from council.settings import current_settings
from council.transport import NO_PROXY_OPENER, read_json

from council_eval.replies import HEADER_KIND, PROMPT_VERSION_FIELD, WINDOW_FIELD
from council_eval.variants import Variant

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TAGS_PATH = "/api/tags"
VERSION_PATH = "/api/version"
GIT_COMMIT = ("git", "rev-parse", "HEAD")
GIT_CHANGES = ("git", "status", "--short", "src/", "measurements/")
TIMEOUT_SECONDS = 30
TURN_START = "cold: the model is unloaded before each item"

Get = Callable[[str], Any]
Run = Callable[[tuple[str, ...]], str]


def get_json(url: str) -> Any:
    """Read one JSON document from the local model server, around the proxy as the product does."""
    with NO_PROXY_OPENER.open(url, timeout=TIMEOUT_SECONDS) as response:
        return read_json(url, response.read().decode("utf-8"))


def git_output(command: tuple[str, ...]) -> str:
    """Run one git query in the repository, refusing to guess if it failed."""
    done = subprocess.run(command, cwd=REPOSITORY_ROOT, capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(f"{' '.join(command)} exited {done.returncode}: {done.stderr.strip()}")
    return done.stdout


def pass_header(
    model: str, dataset: Path, variant: Variant, get: Get = get_json, run: Run = git_output
) -> dict:
    """Describe a pass before it starts: the weights, the server, the pinning, code and data."""
    pinning = LocalModel(model=model)
    return {
        "kind": HEADER_KIND,
        "model": model,
        "digest": model_digest(model, get(f"{pinning.host}{TAGS_PATH}")),
        "ollama": get(f"{pinning.host}{VERSION_PATH}")["version"],
        PROMPT_VERSION_FIELD: variant.prompt_version,
        "temperature": PINNED_TEMPERATURE,
        "seed": pinning.seed,
        WINDOW_FIELD: pinning.context_tokens,
        # Not in the request, so no replay can check it; a slow model's failures hang on it.
        "timeout_seconds": current_settings().timeout_seconds,
        "think": PINNED_THINKING,
        "turn_start": TURN_START,
        "dataset_sha256": file_digest(dataset),
        "commit": run(GIT_COMMIT).strip(),
        "changes": run(GIT_CHANGES).splitlines(),
        "started": now(),
    }


def model_digest(model: str, tags: Any) -> str:
    """Give the digest the server holds for one model, refusing a model it does not have."""
    digests = {entry["name"]: entry["digest"] for entry in tags.get("models", [])}
    if model not in digests:
        raise ValueError(f"the server holds no {model}; it has {', '.join(sorted(digests))}")
    return digests[model]


def file_digest(path: Path) -> str:
    """Fingerprint a file, so a pass names exactly the dataset it read."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now() -> str:
    """Give the wall-clock time with its offset, to the second."""
    return datetime.now().astimezone().isoformat(timespec="seconds")
