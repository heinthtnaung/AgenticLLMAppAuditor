"""Saved calls, read back, and a client that answers the product's runner from them.

A replies file is JSON Lines: a header saying what produced it, then one line
per call. Replaying one through the product's own runner, chairman and record is
what lets a roster be scored without asking a model again, and any roster be
built from passes that each asked one model.

**The replay answers only the request that was recorded.** It rebuilds the
request with the product's `build_request` and refuses a reply whose request
fingerprint differs: a prompt reworded, a redaction widened, or a pinning moved
since the pass would otherwise be scored with answers to a different question.
That refusal is `ReplayMismatch`, which the runner does not catch -- a replay
fault must stop the scoring, never pass as a member that failed.
"""

import json
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Any, Mapping

from council.ollama import LocalModel, build_request, read_answer
from council.prompt import MemberPrompt
from council.roster import Member
from council.transport import ModelUnavailable

from council_eval.recording import CallRecord, request_digest
from council_eval.variants import Variant, variant_prompt

HEADER_KIND = "header"
CALL_KIND = "call"
PROMPT_VERSION_FIELD = "prompt_version"
WINDOW_FIELD = "num_ctx"

CallKey = tuple[str, str, str]


class ReplayMismatch(RuntimeError):
    """A recorded reply does not answer the request the replay would make."""


@dataclass(frozen=True)
class Replies:
    """What passes recorded: each pass's header, and every call by item, model and metric."""

    headers: tuple[Mapping[str, Any], ...]
    calls: Mapping[CallKey, CallRecord]


def call_line(key: str, model: str, record: CallRecord) -> dict[str, Any]:
    """Give one call as a line of a replies file."""
    return {"kind": CALL_KIND, "key": key, "model": model, **vars(record)}


def read_replies(paths: tuple[Path, ...]) -> Replies:
    """Read several replies files into one, refusing two that recorded the same call."""
    lines = list(chain.from_iterable(lines_of(path) for path in paths))
    headers = tuple(line for line in lines if line["kind"] == HEADER_KIND)
    if len(headers) != len(paths):
        raise ValueError(f"{len(paths)} replies files carry {len(headers)} headers")
    calls = [line for line in lines if line["kind"] == CALL_KIND]
    return Replies(headers=headers, calls=calls_by_key(calls))


def lines_of(path: Path) -> list[dict[str, Any]]:
    """Read one replies file, a JSON object per line."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def calls_by_key(lines: list[Mapping[str, Any]]) -> dict[CallKey, CallRecord]:
    """Index recorded calls by item, model and metric, refusing a call recorded twice."""
    keyed = {(line["key"], line["model"], line["metric"]): record_of(line) for line in lines}
    if len(keyed) != len(lines):
        raise ValueError(f"{len(lines) - len(keyed)} calls are recorded more than once")
    return keyed


def record_of(line: Mapping[str, Any]) -> CallRecord:
    """Rebuild one call record from its line."""
    return CallRecord(
        metric=line["metric"],
        request_sha256=line["request_sha256"],
        envelope=line["envelope"],
        seconds=line["seconds"],
    )


@dataclass(frozen=True)
class ReplayClient:
    """A provider client that answers one item's prompts from the calls recorded for it.

    `variant` and `window` are what the passes were asked under: the request is
    rebuilt in that variant's words at that window, so a pass replayed as any
    other variant, or at the window this machine's settings name now, is refused.
    """

    key: str
    calls: Mapping[CallKey, CallRecord]
    variant: Variant
    window: int

    def __call__(self, member: Member, prompt: MemberPrompt) -> str:
        """Answer as the recorded call did, or refuse a request that was never recorded."""
        pinning = LocalModel(model=member.model, context_tokens=self.window)
        # Built first, as `ask` builds it: a prompt the live call refused is refused here.
        asked = variant_prompt(prompt, self.variant)
        request = build_request(asked, pinning)
        recorded = self.recorded(member.model, prompt.metric)
        if recorded.request_sha256 != request_digest(request):
            raise ReplayMismatch(f"{self.key} {prompt.metric}: {member.model} was asked otherwise")
        if recorded.envelope is None:
            raise ModelUnavailable(f"{member.model} sent nothing back for {prompt.metric}")
        return read_answer(recorded.envelope, asked, pinning).text

    def recorded(self, model: str, metric: str) -> CallRecord:
        """Find the call recorded for one model and metric of this item."""
        found = self.calls.get((self.key, model, metric))
        if found is None:
            raise ReplayMismatch(f"no call of {model} on {self.key} {metric} was recorded")
        return found
