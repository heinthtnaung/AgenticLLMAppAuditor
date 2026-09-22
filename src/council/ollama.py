"""The local member: one pinned Ollama model, asked one question over loopback.

**Pinning is the whole point of a local member.** `docs/COUNCIL.md` says a
hosted member cannot be reproduced run to run and a local one can, so the three
things that make that true are set here and are not left to a default: a fixed
model, temperature 0, and a seed. Temperature is a module constant rather than a
field because it is not an option -- a member sampling at 0.8 is a different
instrument, and the record would still call it reproducible.

The context length is set explicitly for the same reason. Ollama's default
window is small enough to truncate a long advisory silently, and an answer given
on half an advisory is wrong in a way no reader can see.

Nothing here parses the model's words: `ask` gives back the reply text and the
model that produced it, and `council.reply` turns that into an answer.
"""

from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlsplit

from council.prompt import MemberPrompt
from council.transport import ModelUnavailable, Transport, post_json

DEFAULT_HOST = "http://127.0.0.1:11434"
GENERATE_PATH = "/api/generate"

DEFAULT_MODEL = "qwen2.5:7b-instruct"
DEFAULT_SEED = 11

# Not a field. See the module docstring: a member that samples is not pinned.
PINNED_TEMPERATURE = 0

# The longest advisory in the corpus is roughly 1,150 tokens and the definitions
# of one metric a few hundred more, so this is several times the worst case.
DEFAULT_CONTEXT_TOKENS = 8192

JSON_REPLY_FORMAT = "json"

LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")

MODEL_FIELD = "model"
RESPONSE_FIELD = "response"
ERROR_FIELD = "error"


@dataclass(frozen=True)
class LocalModel:
    """The pinning of one local member: which model, which seed, how much context."""

    model: str = DEFAULT_MODEL
    seed: int = DEFAULT_SEED
    context_tokens: int = DEFAULT_CONTEXT_TOKENS
    host: str = DEFAULT_HOST

    def __post_init__(self) -> None:
        """Refuse a pinning that is not one, and a host that is not this machine."""
        if not self.model:
            raise ValueError("A local member must name the model it runs")
        if self.context_tokens <= 0:
            raise ValueError(f"{self.model} needs a context length, not {self.context_tokens}")
        refuse_remote_host(self.host)


@dataclass(frozen=True)
class ModelReply:
    """What came back: the words, and the model the server says wrote them."""

    text: str
    model: str


def ask(
    prompt: MemberPrompt,
    pinning: LocalModel | None = None,
    transport: Transport = post_json,
) -> ModelReply:
    """Put one member's prompt to a local model and give back what it said."""
    pinned = pinning or LocalModel()
    envelope = transport(generate_url(pinned), build_request(prompt, pinned))
    return read_envelope(envelope, pinned)


def generate_url(pinning: LocalModel) -> str:
    """Give the generate endpoint of a pinning's host."""
    return f"{pinning.host.rstrip('/')}{GENERATE_PATH}"


def build_request(prompt: MemberPrompt, pinning: LocalModel) -> dict[str, Any]:
    """Build the Ollama request for one prompt, pinned and not streamed."""
    return {
        MODEL_FIELD: pinning.model,
        "system": prompt.system,
        "prompt": prompt.user,
        "stream": False,
        "format": JSON_REPLY_FORMAT,
        "options": {
            "temperature": PINNED_TEMPERATURE,
            "seed": pinning.seed,
            "num_ctx": pinning.context_tokens,
        },
    }


def read_envelope(envelope: Any, pinning: LocalModel) -> ModelReply:
    """Read Ollama's reply envelope, refusing one that carries no answer."""
    if not isinstance(envelope, Mapping):
        raise ModelUnavailable(f"{pinning.model} returned {type(envelope).__name__}, not an object")
    if envelope.get(ERROR_FIELD):
        raise ModelUnavailable(f"{pinning.model} refused the request: {envelope[ERROR_FIELD]}")
    text = envelope.get(RESPONSE_FIELD)
    if not isinstance(text, str) or not text.strip():
        raise ModelUnavailable(f"{pinning.model} answered with no text at all")
    return ModelReply(text=text, model=envelope.get(MODEL_FIELD) or pinning.model)


def refuse_remote_host(host: str) -> None:
    """Refuse a host that is not this machine, so 'ran local' on a record is never a lie."""
    hostname = urlsplit(host).hostname
    if hostname in LOOPBACK_HOSTS:
        return
    raise ValueError(
        f"{host!r} is not this machine: an Ollama member records ran_local, so it may only "
        f"talk to {', '.join(LOOPBACK_HOSTS[:2])}. A model elsewhere is a hosted member."
    )
