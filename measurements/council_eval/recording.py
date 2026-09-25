"""Asking a local member exactly as the product does, and keeping every envelope that came back.

The client here is the product's own `council.ollama.ask` with one thing
swapped: the transport, which posts through the product's `post_json` and keeps
what it sent and what came home. So the request -- the prompt, the pinning, the
thinking setting -- is built by the code under measurement, never by this file,
and the saved envelope is what the product then read.

**A member's turn starts from a freshly loaded model.** Measured on Ollama
0.34.3 on the GPU, `qwen2.5:7b-instruct` answers one prompt differently cold
and straight after the same prompt, at temperature 0 with a seed.
`measurements/council_runs/gpu-full` began every member's turn on a fresh load,
because the two members did not fit in memory together. Unloading before each
turn recreates that, and it is what makes one pass per model independent of
every other model's pass.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from council.ollama import LocalModel, ask, generate_url
from council.prompt import MemberPrompt
from council.roster import Member
from council.transport import post_json

# The token ids of the prompt and reply. Long, and nothing downstream reads them.
DROPPED_FIELDS = ("context",)
UNLOADED = "unload"
# No request was made: the product refused the prompt before sending it.
NO_REQUEST = ""

Post = Callable[[str, dict[str, Any]], Any]


@dataclass(frozen=True)
class CallRecord:
    """One call to one member: what was sent, what came back, and how long it took.

    `envelope` is None only when nothing came back -- the prompt was refused
    before sending, or the server could not be reached -- and then
    `request_sha256` says which: `NO_REQUEST` for the first.
    """

    metric: str
    request_sha256: str
    envelope: Mapping[str, Any] | None
    seconds: float


def request_digest(payload: Mapping[str, Any]) -> str:
    """Fingerprint a request, so a replay can refuse a reply recorded for a different one."""
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


class RecordingTransport:
    """The product's transport, keeping the request it posted and the envelope it got back."""

    def __init__(self, post: Post = post_json) -> None:
        """Start with nothing sent."""
        self.post = post
        self.request_sha256 = NO_REQUEST
        self.envelope: dict[str, Any] | None = None

    def __call__(self, url: str, payload: dict[str, Any]) -> Any:
        """Post one request as the product would, and keep both halves."""
        self.request_sha256 = request_digest(payload)
        envelope = self.post(url, payload)
        self.envelope = kept(envelope)
        return envelope


def kept(envelope: Any) -> Any:
    """Keep an envelope whole, but for the token ids nothing reads."""
    if not isinstance(envelope, Mapping):
        return envelope
    return {name: value for name, value in envelope.items() if name not in DROPPED_FIELDS}


@dataclass
class RecordingClient:
    """A provider client for the product's runner that asks through `ask` and keeps every call."""

    post: Post = post_json
    clock: Callable[[], float] = time.monotonic
    calls: list[CallRecord] = field(default_factory=list)

    def __call__(self, member: Member, prompt: MemberPrompt) -> str:
        """Ask one member one prompt, recording the call whether or not it succeeds."""
        transport = RecordingTransport(self.post)
        started = self.clock()
        try:
            return ask(prompt, LocalModel(model=member.model), transport).text
        finally:
            elapsed = self.clock() - started
            sent = transport.request_sha256
            self.calls.append(CallRecord(prompt.metric, sent, transport.envelope, elapsed))


def unload_model(model: str, post: Post = post_json) -> None:
    """Unload a model, so its next call starts from a fresh load, refusing a server that did not."""
    pinning = LocalModel(model=model)
    envelope = post(generate_url(pinning), {"model": pinning.model, "keep_alive": 0})
    said = envelope.get("done_reason") if isinstance(envelope, Mapping) else envelope
    if said != UNLOADED:
        raise RuntimeError(f"asked to unload {model}, the server answered {said!r}")
