"""Pasted replies written as a pass: a header, each reply as saved, each metric as a call.

The shape is `collect`'s, so `score`, `order-checked` and `grades` read it as they
read any pass. Where a local pass records an observation a chat cannot give --
the weights' digest, the pinning, the window, the time a call took -- this
records that it is unknown rather than a number, and the header says what else
cannot be checked. The reply is kept whole beside its calls, so every call
re-derives from the line above it, and that line from the saved file.
"""

import json
from itertools import chain
from typing import Any, Mapping

from council.envelope import RESPONSE_FIELD
from council.prompt import PROMPT_VERSION
from council_eval.chat_passes import AnsweredPrompt
from council_eval.collect import END_KIND
from council_eval.pass_provenance import GIT_CHANGES, GIT_COMMIT, Run, git_output
from council_eval.recording import CallRecord
from council_eval.replies import HEADER_KIND, PROMPT_VERSION_FIELD, WINDOW_FIELD, call_line
from council_eval.variants import Variant
from cvss.metrics import METRIC_ORDER

PASTED_KIND = "pasted"
# What a local pass pins and a chat does not say.
UNKNOWN_PINNING = ("temperature", "seed", WINDOW_FIELD, "think")
REPLY_SHA256_FIELD = "reply_sha256"
UNKNOWN = "unknown"
UNKNOWN_WEIGHTS = "unknown: a chat interface names no weights"
NO_SERVER = "none: pasted by a person into a chat interface"
FRESH_CHAT = "a fresh chat per prompt, by the pasting procedure; not checked"
CHAT_PROVENANCE = "chat interface; weights, temperature and seed unknown"
BROWSING_UNCHECKED = "not checked: nothing in a pasted reply shows whether the chat searched"
ONE_MESSAGE = (
    "all eight metrics in one message, the definitions beside the advisory; not the local "
    f"council's {PROMPT_VERSION}, one metric per call, the definitions in a turn of their own"
)

INTERFACE_FIELD = "interface"
ENDED_FIELD = "ended"
PROVENANCE_FIELD = "provenance"
BROWSING_FIELD = "web_browsing"
SHAPE_FIELD = "prompt_shape"
# Printed beside a pass's pinning where its header carries them, which only a pasted one does.
PASTED_HEADER_FIELDS = (
    INTERFACE_FIELD, ENDED_FIELD, PROVENANCE_FIELD, BROWSING_FIELD, SHAPE_FIELD,
)


def pass_lines(
    answered: tuple[AnsweredPrompt, ...], variant: Variant, dataset_sha256: str,
    run: Run = git_output,
) -> list[Mapping[str, Any]]:
    """Give one order's pass: its header, each reply and its eight calls, and an end line."""
    ordered = variant.reversed_options
    mine = tuple(one for one in answered if one.prompt.reversed_options == ordered)
    header = chat_header(mine, variant, dataset_sha256, run)
    body = list(chain.from_iterable(item_lines(one) for one in mine))
    return [header, *body, {"kind": END_KIND, "calls": len(mine) * len(METRIC_ORDER)}]


def chat_header(
    answered: tuple[AnsweredPrompt, ...], variant: Variant, dataset_sha256: str, run: Run
) -> dict[str, Any]:
    """Describe a pasted pass: the model and interface as typed, and everything left unknown."""
    first = answered[0].reply.saved
    dates = sorted(one.reply.saved.date for one in answered)
    return {
        "kind": HEADER_KIND,
        "model": first.model,
        "digest": UNKNOWN_WEIGHTS,
        "ollama": NO_SERVER,
        PROMPT_VERSION_FIELD: variant.prompt_version,
        **{name: UNKNOWN for name in UNKNOWN_PINNING},
        "turn_start": FRESH_CHAT,
        "dataset_sha256": dataset_sha256,
        "commit": run(GIT_COMMIT).strip(),
        "changes": run(GIT_CHANGES).splitlines(),
        "started": dates[0],
        ENDED_FIELD: dates[-1],
        INTERFACE_FIELD: first.interface,
        PROVENANCE_FIELD: CHAT_PROVENANCE,
        BROWSING_FIELD: BROWSING_UNCHECKED,
        SHAPE_FIELD: ONE_MESSAGE,
    }


def item_lines(answered: AnsweredPrompt) -> list[Mapping[str, Any]]:
    """Give one reply as saved, then each of its metrics as a call."""
    model = answered.reply.saved.model
    key = answered.prompt.key
    calls = [call_line(key, model, call_of(answered, one)) for one in METRIC_ORDER]
    return [pasted_line(answered), *calls]


def pasted_line(answered: AnsweredPrompt) -> dict[str, Any]:
    """Record one reply whole: its file, its date, its fingerprint and every byte of it."""
    saved, prompt = answered.reply.saved, answered.prompt
    return {
        "kind": PASTED_KIND, "key": prompt.key, "model": saved.model, "file": saved.file,
        "prompt_file": prompt.file, "prompt_id": prompt.prompt_id,
        "prompt_sha256": prompt.sha256, "order": prompt.order, "date": saved.date,
        REPLY_SHA256_FIELD: saved.sha256, "reply": saved.reply,
    }


def call_of(answered: AnsweredPrompt, metric: str) -> CallRecord:
    """Record one metric of a reply as a call: the prompt it answered, and its three fields."""
    said = json.dumps(answered.reply.readings[metric], sort_keys=True)
    return CallRecord(
        metric=metric,
        request_sha256=answered.prompt.sha256,
        envelope={RESPONSE_FIELD: said, REPLY_SHA256_FIELD: answered.reply.saved.sha256},
        seconds=None,
    )
