"""Reading what Ollama sent back into the reply's words, or into a failure that says why.

A member either answered or failed, and a failure carries the server's own
account of it, because the operator trying a newer model reads that account to
learn what went wrong. An envelope carries no answer in four ways, each a
`ModelUnavailable` the runner records as a member that failed:

- **it is not an envelope** -- the server returned something other than an object;
- **the server refused** -- an `error` field. Measured on Ollama 0.34.3, a model
  that cannot generate (`nomic-embed-text`) and a `think` the model does not
  support are both refused with HTTP 400 instead, which `council.transport`
  turns into the same failure, quoting the server;
- **the model was cut off** -- `done_reason` is `length`. The model had not
  finished, so the text may be the start of an answer or of its reasoning, and
  neither is an answer. Every one of the 1,728 envelopes the council evaluation
  recorded stopped with `stop`;
- **it said nothing** -- no text in `response`, however much it put elsewhere.

**`thinking` is never read as the answer.** Ollama returns a model's reasoning
there -- measured: `gemma4:latest`, asked with `think` true and no `format`,
sent 2,957 characters of it beside its answer -- and only `response` is the
reply the prompt asked for. What an unusable envelope did hold is named in the
failure -- how much reply, how much thinking, and why it stopped -- so a model
that spent its turn reasoning reads as that and not as a silent server.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from council.transport import ModelUnavailable

MODEL_FIELD = "model"
RESPONSE_FIELD = "response"
ERROR_FIELD = "error"
THINKING_FIELD = "thinking"
DONE_REASON_FIELD = "done_reason"
PROMPT_COUNT_FIELD = "prompt_eval_count"
CUT_OFF = "length"


class Pinned(Protocol):
    """Whatever names the model a member was pinned to, which a failure is said of."""

    model: str


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


def read_envelope(envelope: Any, pinning: Pinned) -> ModelReply:
    """Read Ollama's reply envelope, refusing one that carries no finished answer."""
    if not isinstance(envelope, Mapping):
        raise ModelUnavailable(f"{pinning.model} returned {type(envelope).__name__}, not an object")
    if envelope.get(ERROR_FIELD):
        raise ModelUnavailable(f"{pinning.model} refused the request: {envelope[ERROR_FIELD]}")
    if envelope.get(DONE_REASON_FIELD) == CUT_OFF:
        raise ModelUnavailable(f"{pinning.model} was cut off before it finished: {held(envelope)}")
    text = envelope.get(RESPONSE_FIELD)
    if not isinstance(text, str) or not text.strip():
        raise ModelUnavailable(f"{pinning.model} answered with no text at all: {held(envelope)}")
    return ModelReply(text=text, model=envelope.get(MODEL_FIELD) or pinning.model)


def held(envelope: Mapping[str, Any]) -> str:
    """Say what an unusable envelope held: how much reply, how much thinking, why it stopped."""
    reply = str(envelope.get(RESPONSE_FIELD) or "")
    thinking = str(envelope.get(THINKING_FIELD) or "")
    stopped = envelope.get(DONE_REASON_FIELD)
    return (
        f"{len(reply)} characters of reply and {len(thinking)} of thinking, "
        f"with {DONE_REASON_FIELD} {stopped!r}"
    )
