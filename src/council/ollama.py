"""The local member: one pinned Ollama model, asked one question over loopback.

**Pinning is the whole point of a local member.** `docs/COUNCIL.md` says a
hosted member cannot be reproduced run to run and a local one can, so the four
things that make that true are set here and are not left to a default: a fixed
model, temperature 0, a seed, and no thinking. Temperature, seed and thinking
are constants here rather than settings -- a member sampling at 0.8 is a
different instrument, and the record would still call it reproducible. The
server, the window and the timeout are the operator's, in `council.settings`.

**Thinking is off for every member, because the default differs by model.**
On Ollama 0.34.3, `gemma4:latest` answers the one prompt probed without `think`
exactly as with `think: true` -- 554 prompt tokens, the same reply byte for
byte, no `thinking` field -- where `think: false` gives 552 and another reply;
that the two tokens mark thinking mode is inferred. Qwen and Llama replied the
same either way in one load state; see `measurements/thinking_and_load/`.

The context length is pinned for the same reason, and `build_request` refuses a
prompt too long for it. An advisory that overflows the window is cut
by the server without saying so, and a member then assesses half an advisory and
answers with confidence -- the record shows an assessment and nothing shows that
most of the text was missing. Measured on Ollama 0.34.3: 9,378 tokens against the
8,192 pinned were cut to 4,098 and answered with a 200. Refusing costs that one
metric, which the chairman records as unresolved and falls back on. The two are
not worth the same, so the refusal is a guard and not a warning -- and because
the guard's estimate is rough, `ask` holds it to the server's own count as well.

Nothing here parses the model's words: `ask` gives back the reply text and the
model the server named beside it, read by `council.envelope`, and `council.reply`
turns those into an answer.
"""

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from council.envelope import MODEL_FIELD, PROMPT_COUNT_FIELD, ModelReply, read_envelope
from council.prompt import MemberPrompt
from council.settings import LOOPBACK_HOSTS, current_settings
from council.transport import ModelUnavailable, Transport, post_json

GENERATE_PATH = "/api/generate"

# Not settings, and not fields but the seed. See the module docstring: a member
# that samples, draws another seed, or thinks by its own default is not pinned.
PINNED_TEMPERATURE = 0
PINNED_SEED = 11
# Sent to every model, so no model's own default decides.
PINNED_THINKING = False

# Four characters to the token. Rough, and every model counts its own way: the
# worst advisory, estimated at 4,936, Qwen counts 0.8% under, Llama 2.9% under
# and Gemma 15.3% over; over the saved passes Qwen runs -17% to +15%, Gemma to
# +23%. `measurements/prompt_tokens.py` re-counts it against any model named.
CHARACTERS_PER_TOKEN = 4

# What the estimate is allowed to be wrong by, in the direction that matters. A
# prompt refused that would just have fitted costs one metric; a prompt sent
# that does not fit costs an assessment of half an advisory that reads like a
# whole one. At 23% over the estimate, the most measured, a prompt at this
# limit still leaves 600 of 8,192 tokens for a reply; the longest recorded is 121.
USABLE_CONTEXT_FRACTION = 0.75

# Ollama cuts a prompt too long for the window to half the window, so the model
# then counts it at under 62% of the estimate for any tokenizer measured; none
# counted a whole prompt at under 83%. Between the two is where a cut shows.
CUT_PROMPT_FRACTION = 0.7

JSON_REPLY_FORMAT = "json"


@dataclass(frozen=True)
class LocalModel:
    """The pinning of one local member: which model, which seed, how much context, which host.

    `host` is here with the other three because it is pinned in the same sense:
    `refuse_remote_host` holds it to loopback, and that is what makes `ran_local`
    on a record an observation rather than a label.
    """

    # The operator's where none is given: `council.settings`, read once a process.
    model: str = field(default_factory=lambda: current_settings().model)
    seed: int = PINNED_SEED
    context_tokens: int = field(default_factory=lambda: current_settings().context_tokens)
    host: str = field(default_factory=lambda: current_settings().server)

    def __post_init__(self) -> None:
        """Refuse a pinning that is not one, and a host that is not this machine."""
        if not self.model:
            raise ValueError("A local member must name the model it runs")
        if self.context_tokens <= 0:
            raise ValueError(f"{self.model} needs a context length, not {self.context_tokens}")
        refuse_remote_host(self.host)


def ask(
    prompt: MemberPrompt,
    pinning: LocalModel | None = None,
    transport: Transport = post_json,
) -> ModelReply:
    """Put one member's prompt to a local model and give back what it said."""
    pinned = pinning or LocalModel()
    envelope = transport(generate_url(pinned), build_request(prompt, pinned))
    return read_answer(envelope, prompt, pinned)


def read_answer(envelope: Any, prompt: MemberPrompt, pinning: LocalModel) -> ModelReply:
    """Read the reply to one prompt, refusing it if the server did not read the prompt whole."""
    reply = read_envelope(envelope, pinning)
    refuse_cut_prompt(envelope.get(PROMPT_COUNT_FIELD), prompt, pinning)
    return reply


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
        # Beside the options, not among them: Ollama reads `think` at the top level.
        "think": PINNED_THINKING,
        "options": {
            "temperature": PINNED_TEMPERATURE,
            "seed": pinning.seed,
            "num_ctx": pinning.context_tokens,
        },
    }


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


def refuse_cut_prompt(counted: Any, prompt: MemberPrompt, pinning: LocalModel) -> None:
    """Refuse an answer to a prompt the server read only part of, having cut it without an error."""
    # Ollama counts the cached part of a prompt too -- a warm Qwen call read 532
    # with 531 cached -- and a server reporting no count cannot be held to one.
    if not isinstance(counted, int):
        return
    estimated = estimated_tokens(prompt)
    if counted >= estimated * CUT_PROMPT_FRACTION:
        return
    raise ModelUnavailable(
        f"{pinning.model} read this {prompt.metric} prompt as {counted} tokens, where about "
        f"{estimated} were sent: Ollama cut it to fit the {pinning.context_tokens} pinned, and "
        f"an answer to part of an advisory is not an answer to the advisory"
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
