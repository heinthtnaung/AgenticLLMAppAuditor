"""The local member: one pinned Ollama model, asked one question over loopback.

**Pinning is the whole point of a local member.** `docs/COUNCIL.md` says a
hosted member cannot be reproduced run to run and a local one can, so the three
things that make that true are set here and are not left to a default: a fixed
model, temperature 0, and a seed. Temperature is a module constant rather than a
field because it is not an option -- a member sampling at 0.8 is a different
instrument, and the record would still call it reproducible.

The context length is set explicitly for the same reason, and `build_request`
refuses a prompt too long for it. An advisory that overflows the window is cut
by the server without saying so, and a member then assesses half an advisory and
answers with confidence -- the record shows an assessment and nothing shows that
most of the text was missing. Refusing costs that one metric, which the chairman
records as unresolved and falls back on. The two are not worth the same, so the
refusal is a guard and not a warning.

Nothing here parses the model's words: `ask` gives back the reply text and the
model the server named beside it -- see `ModelReply` for what that name is worth
-- and `council.reply` turns those into an answer.
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

# Measured, and pinned rather than generous. The pinned model counts the whole
# prompt -- one metric's definitions, the instructions and the reply schema --
# at 421 tokens with the advisory taken out, and the worst advisory of 1,187
# read off this machine's database snapshot takes it to 4,897. So the margin is
# 1.7x, not the several times an 18-advisory corpus suggested.
#
# It stays at 8,192 anyway. The window is one of the things a local member pins,
# and `docs/COUNCIL.md` rests the reproducibility claim on the pinning, so
# moving it changes what a run is comparable with. `refuse_overlong_prompt`
# below makes the failure impossible instead of rare, and its firing is the
# evidence that would justify raising this -- nothing has come near the limit
# yet, and the day something does is the day to raise it knowingly.
DEFAULT_CONTEXT_TOKENS = 8192

# Four characters to the token. Rough, and calibrated: on the worst advisory in
# the corpus this estimate said 4,936 where the model counted 4,897, an error of
# 0.8%. `measurements/prompt_tokens.py` re-counts it against the pinned model.
CHARACTERS_PER_TOKEN = 4

# What the estimate is allowed to be wrong by, in the direction that matters. A
# prompt refused that would just have fitted costs one metric; a prompt sent
# that does not fit costs an assessment of half an advisory that reads like a
# whole one.
USABLE_CONTEXT_FRACTION = 0.9

JSON_REPLY_FORMAT = "json"

LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")

MODEL_FIELD = "model"
RESPONSE_FIELD = "response"
ERROR_FIELD = "error"


@dataclass(frozen=True)
class LocalModel:
    """The pinning of one local member: which model, which seed, how much context, which host.

    `host` is here with the other three because it is pinned in the same sense:
    `refuse_remote_host` holds it to loopback, and that is what makes `ran_local`
    on a record an observation rather than a label.
    """

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
    """What came back: the words, and which model answered -- if the server said.

    `model` is the name the server reported, and the pinned name when it
    reported none. Those are an observation and a claim, and this field does not
    distinguish them. It matters because `docs/COUNCIL.md` rests reproducibility
    on knowing which weights answered: a record saying `qwen2.5:7b-instruct`
    may mean the server confirmed it or only that nobody contradicted it. Ollama
    does name the model on every reply seen so far, so the fallback is for a
    server that stops -- it is not the ordinary path, and it is not a lie the
    reader can spot.
    """

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
    """Build the Ollama request for one prompt, pinned, not streamed, and sure to fit."""
    refuse_overlong_prompt(prompt, pinning)
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


def estimated_tokens(prompt: MemberPrompt) -> int:
    """Estimate what a prompt will cost the model to read, in tokens."""
    return (len(prompt.system) + len(prompt.user)) // CHARACTERS_PER_TOKEN


def refuse_overlong_prompt(prompt: MemberPrompt, pinning: LocalModel) -> None:
    """Refuse a prompt the window cannot hold, rather than let the server cut it in silence."""
    estimated = estimated_tokens(prompt)
    usable = int(pinning.context_tokens * USABLE_CONTEXT_FRACTION)
    if estimated <= usable:
        return
    raise ValueError(
        f"This {prompt.metric} prompt is roughly {estimated} tokens, about "
        f"{estimated - usable} more than the {usable} usable of the {pinning.context_tokens} "
        f"{pinning.model} is pinned to. Ollama would cut it without saying so and the member "
        f"would assess part of the advisory as though it were all of it. Shorten the "
        f"advisory, or raise the pinned context knowing it changes what the run compares to."
    )


def refuse_remote_host(host: str) -> None:
    """Refuse a host that is not this machine, so 'ran local' on a record is never a lie."""
    hostname = urlsplit(host).hostname
    if hostname in LOOPBACK_HOSTS:
        return
    raise ValueError(
        f"{host!r} is not this machine: an Ollama member records ran_local, so it may only "
        f"talk to {', '.join(LOOPBACK_HOSTS[:2])}. A model elsewhere is a hosted member."
    )
