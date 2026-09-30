"""What produced a pass, written as its first line before any model is asked.

Every figure scored from a pass carries this beside it: which weights answered
(the digest the server reports, not the tag), which server, the pinning the
product actually sends, the prompt version, the dataset's fingerprint, and the
code -- the commit and whatever in `src/` and `measurements/` was not committed.
A figure nobody can re-derive is not a measurement. The prompt version is the
variant's, which begins with the product's version it was made from.

The pinning is read from the product's own constants and `LocalModel`, never
restated here, so a pass cannot claim a seed or a temperature the request did
not carry. The two reads of the server are the product's too: its list of models
and its version, as `cli.model_identity` reads them through `council.transport`.
**What differs is the verdict.** An audit records a digest it could not read as
unknown and goes on; a pass refuses to start, because a figure scored from
weights nobody named is not a measurement.
"""

import hashlib
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable

from cli.model_identity import Listing, Read, listing_of, server_version
from council.ollama import PINNED_TEMPERATURE, PINNED_THINKING, LocalModel
from council.settings import current_settings
from council.transport import get_json
from report.model_identity import UnknownOllamaVersion

from council_eval.replies import HEADER_KIND, PROMPT_VERSION_FIELD, WINDOW_FIELD
from council_eval.variants import Variant

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GIT_COMMIT = ("git", "rev-parse", "HEAD")
GIT_CHANGES = ("git", "status", "--short", "src/", "measurements/")
TURN_START = "cold: the model is unloaded before each item"

Run = Callable[[tuple[str, ...]], str]


def git_output(command: tuple[str, ...]) -> str:
    """Run one git query in the repository, refusing to guess if it failed."""
    done = subprocess.run(command, cwd=REPOSITORY_ROOT, capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(f"{' '.join(command)} exited {done.returncode}: {done.stderr.strip()}")
    return done.stdout


def pass_header(
    model: str, dataset: Path, variant: Variant, get: Read = get_json, run: Run = git_output
) -> dict:
    """Describe a pass before it starts: the weights, the server, the pinning, code and data."""
    pinning = LocalModel(model=model)
    return {
        "kind": HEADER_KIND,
        "model": model,
        "digest": model_digest(model, held_listing(pinning.host, get)),
        "ollama": held_version(pinning.host, get),
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


def held_listing(host: str, get: Read) -> Listing:
    """Read the server's models as an audit does, refusing a list that could not be read."""
    listing = listing_of(host, get)
    if listing.unread:
        raise ValueError(f"a pass must name its weights, and {listing.unread}")
    return listing


def held_version(host: str, get: Read) -> str:
    """Read the server's version as an audit does, refusing a server that gave none."""
    version = server_version(host, get)
    if isinstance(version, UnknownOllamaVersion):
        raise ValueError(f"a pass must name its server, and {version.reason}")
    return version.version


def model_digest(model: str, listing: Listing) -> str:
    """Give the digest the server lists under exactly this name, refusing any other."""
    # The name as given, not `cli.model_identity.tagged`'s reading of it: a pass
    # is keyed by the name it was asked under, so `llama3.2` is refused where the
    # server lists `llama3.2:latest`, rather than recorded under a tag it assumed.
    if model in listing.digests:
        return listing.digests[model]
    if model in listing.names:
        raise ValueError(f"the server lists {model} without a digest, so no pass can name it")
    raise ValueError(f"the server holds no {model}; it has {', '.join(sorted(listing.names))}")


def file_digest(path: Path) -> str:
    """Fingerprint a file, so a pass names exactly the dataset it read."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now() -> str:
    """Give the wall-clock time with its offset, to the second."""
    return datetime.now().astimezone().isoformat(timespec="seconds")
