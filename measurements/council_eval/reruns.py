"""Two passes of one model side by side: the same requests, and the same replies byte for byte?

A pinned local member claims to reproduce its replies, and two passes over one
dataset are the test of that claim. The measure is strict: the reply text as
the server returned it, compared byte for byte, beside the fingerprint of the
request that produced it.

**A call reloaded in the middle of an item is named.** Every item starts from
a fresh load, so only its first call should spend time loading. A later call
that did was asked in another load state than the protocol claims -- another
client evicted the model -- and a reader weighing the comparison needs to know
which calls those were.
"""

from dataclasses import dataclass
from typing import Mapping

from cvss.metrics import METRIC_ORDER

from council_eval.recording import CallRecord
from council_eval.replies import CallKey, Replies

NANOSECONDS = 1e9
# A warm call loads in milliseconds; a load from memory took 3 s or more here.
LOADED_SECONDS = 1.0


@dataclass(frozen=True)
class RerunComparison:
    """How two passes of one model compare, call by call."""

    model: str
    calls: int
    same_request: int
    identical: int
    unanswered: int
    differing: tuple[CallKey, ...]
    reloaded_first: tuple[CallKey, ...]
    reloaded_second: tuple[CallKey, ...]


def compare_passes(first: Replies, second: Replies) -> RerunComparison:
    """Compare two passes of one model over one dataset, refusing passes that asked otherwise."""
    model = only_model(first, second)
    if sorted(first.calls) != sorted(second.calls):
        raise ValueError("the two passes did not record the same calls")
    pairs = [(key, first.calls[key], second.calls[key]) for key in sorted(first.calls)]
    return RerunComparison(
        model=model,
        calls=len(pairs),
        same_request=sum(one.request_sha256 == other.request_sha256 for _, one, other in pairs),
        identical=sum(same_reply(one, other) for _, one, other in pairs),
        unanswered=sum(not answered(one, other) for _, one, other in pairs),
        differing=tuple(key for key, one, other in pairs if differs(one, other)),
        reloaded_first=reloaded(first.calls),
        reloaded_second=reloaded(second.calls),
    )


def only_model(first: Replies, second: Replies) -> str:
    """Give the one model both passes asked, refusing any other pairing."""
    models = {header["model"] for header in (*first.headers, *second.headers)}
    if len(first.headers) != 1 or len(second.headers) != 1 or len(models) != 1:
        raise ValueError(f"a rerun compares two passes of one model, not {sorted(models)}")
    return models.pop()


def answered(one: CallRecord, other: CallRecord) -> bool:
    """Say whether both calls got an envelope back."""
    return one.envelope is not None and other.envelope is not None


def same_reply(one: CallRecord, other: CallRecord) -> bool:
    """Say whether two calls got the same reply text back, byte for byte."""
    return answered(one, other) and one.envelope.get("response") == other.envelope.get("response")


def differs(one: CallRecord, other: CallRecord) -> bool:
    """Say whether two calls that both got an answer got different ones."""
    return answered(one, other) and not same_reply(one, other)


def reloaded(calls: Mapping[CallKey, CallRecord]) -> tuple[CallKey, ...]:
    """Name the calls, after an item's first, that spent time loading the model."""
    later = [key for key in sorted(calls) if key[2] != METRIC_ORDER[0]]
    return tuple(key for key in later if load_seconds(calls[key]) > LOADED_SECONDS)


def load_seconds(record: CallRecord) -> float:
    """Give how long a call spent loading the model, and none for a call that got nothing back."""
    if record.envelope is None:
        return 0.0
    return record.envelope.get("load_duration", 0) / NANOSECONDS
