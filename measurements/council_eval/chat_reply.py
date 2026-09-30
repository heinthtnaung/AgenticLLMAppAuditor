"""The one fenced JSON block in a pasted reply, read into eight metrics or refused loudly.

Prose around the block is tolerated: the chat narrates, and the block is still
the block. **Anything else that does not fit is refused**, naming the file: no
block or two, a block that is not a JSON object, a key named twice, a metric
missing or a key no reply format asks for, a field missing or added, a letter the metric does not
allow, a confidence the prompt never offered. A refusal is the person's to
settle -- ask again in a fresh chat -- and never this code's to repair.

Each metric's value is read as `council.reply` reads a member's -- the letter
alone or the whole `AV:N` pair, in any case -- and held to the letters
`cvss.metrics` allows. Its quotation is kept as the chat gave it and checked
later, by the chairman, against the advisory the chat was shown.
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

from council.reply import read_value
from council.reply_format import (
    CONFIDENCE_FIELD,
    CONFIDENCE_WORDS,
    EVIDENCE_FIELD,
    NO_EVIDENCE_VALUE,
    REQUIRED_FIELDS,
)
from council_eval.chat_prompt import PROMPT_ID_FIELD
from council_eval.chat_reply_file import RefusedReply, SavedReply
from cvss.metrics import METRIC_ORDER, refuse_illegal_pair

# A fence opens on a line of three backticks, with or without a language, and
# closes on a line of three backticks alone.
FENCED_BLOCK = re.compile(r"^[ \t]*```[^\n`]*\n(.*?)^[ \t]*```[ \t]*$", re.MULTILINE | re.DOTALL)
REPLY_KEYS = (PROMPT_ID_FIELD, *METRIC_ORDER)


@dataclass(frozen=True)
class ChatReply:
    """A saved reply read: the prompt it names, and each metric's three fields as given."""

    saved: SavedReply
    prompt_id: str
    readings: Mapping[str, Mapping[str, str]]


def read_chat_reply(saved: SavedReply) -> ChatReply:
    """Read the one fenced block of a saved reply into its prompt ID and eight metrics."""
    fields = decoded_block(saved)
    refuse_keys(fields, saved.file)
    readings = {one: checked_metric(fields[one], one, saved.file) for one in METRIC_ORDER}
    return ChatReply(saved, checked_prompt_id(fields[PROMPT_ID_FIELD], saved.file), readings)


def decoded_block(saved: SavedReply) -> Mapping[str, Any]:
    """Find the reply's one fenced block and decode it, refusing none, two, or not an object."""
    blocks = FENCED_BLOCK.findall(saved.reply)
    if not blocks:
        raise RefusedReply(saved.file, "holds no fenced JSON block; copy the reply whole")
    if len(blocks) > 1:
        raise RefusedReply(saved.file, f"holds {len(blocks)} fenced blocks, and one was asked for")
    try:
        decoded = json.loads(blocks[0], object_pairs_hook=unrepeated)
    except json.JSONDecodeError as fault:
        raise RefusedReply(saved.file, f"its fenced block is not JSON ({fault})") from fault
    except ValueError as fault:
        raise RefusedReply(saved.file, f"its block {fault}") from fault
    if not isinstance(decoded, dict):
        raise RefusedReply(saved.file, f"its block is a {type(decoded).__name__}, not an object")
    return decoded


def unrepeated(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build one JSON object, refusing a key named twice, which `json` would settle silently."""
    # A reply drafting AV and then restating it would otherwise be read as its last word.
    keys = [key for key, _ in pairs]
    repeated = sorted({key for key in keys if keys.count(key) > 1})
    if repeated:
        raise ValueError(f"names {', '.join(repeated)} more than once")
    return dict(pairs)


def refuse_keys(fields: Mapping[str, Any], file: str) -> None:
    """Refuse a block missing a metric or the prompt ID, or carrying a key nobody asked for."""
    missing = [key for key in REPLY_KEYS if key not in fields]
    if missing:
        raise RefusedReply(file, f"its block has no {', '.join(missing)}")
    unknown = sorted(key for key in fields if key not in REPLY_KEYS)
    if unknown:
        raise RefusedReply(file, f"its block names {', '.join(unknown)}, which is no Base metric")


def checked_prompt_id(given: Any, file: str) -> str:
    """Read the prompt ID the reply repeats, refusing one that is not text."""
    if not isinstance(given, str) or not given.strip():
        raise RefusedReply(file, f"its {PROMPT_ID_FIELD} is {given!r}, not a prompt's ID")
    return given.strip().lower()


def checked_metric(given: Any, metric: str, file: str) -> Mapping[str, str]:
    """Hold one metric's answer to its three fields, a legal value, text, and a confidence word."""
    if not isinstance(given, dict):
        raise RefusedReply(file, f"{metric} is a {type(given).__name__}, not an object")
    refuse_fields(given, metric, file)
    refuse_illegal_value(given, metric, file)
    if not isinstance(given[EVIDENCE_FIELD], str):
        raise RefusedReply(file, f"{metric}'s {EVIDENCE_FIELD} is not text")
    refuse_unoffered_confidence(given[CONFIDENCE_FIELD], metric, file)
    return given


def refuse_fields(given: Mapping[str, Any], metric: str, file: str) -> None:
    """Refuse a metric's answer missing a field of the reply format, or adding one."""
    missing = [name for name in REQUIRED_FIELDS if name not in given]
    if missing:
        raise RefusedReply(file, f"{metric} has no {', '.join(missing)}")
    added = sorted(name for name in given if name not in REQUIRED_FIELDS)
    if added:
        raise RefusedReply(file, f"{metric} adds {', '.join(added)}, which the format never asks")


def refuse_illegal_value(given: Mapping[str, Any], metric: str, file: str) -> None:
    """Refuse a value that is neither a letter this metric allows nor NO_EVIDENCE."""
    try:
        value = read_value(given, metric)
        if value != NO_EVIDENCE_VALUE:
            refuse_illegal_pair(metric, value)
    # `MalformedReply` is a `ValueError`, as the refusal of an illegal letter is.
    except ValueError as fault:
        raise RefusedReply(file, f"{metric}: {fault}") from fault


def refuse_unoffered_confidence(given: Any, metric: str, file: str) -> None:
    """Refuse a confidence that is not one of the words the prompt offers."""
    if isinstance(given, str) and given.strip().lower() in CONFIDENCE_WORDS:
        return
    offered = ", ".join(CONFIDENCE_WORDS)
    raise RefusedReply(file, f"{metric}'s {CONFIDENCE_FIELD} {given!r} is none of {offered}")
