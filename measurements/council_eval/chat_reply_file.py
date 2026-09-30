"""A reply a person saved from a chat: whom they asked, when, through what, and what came back.

The file is a short header the person writes, a line of `---`, and then the
whole reply as the chat's copy button gave it:

    model: the model's name, as the chat names it
    date: 2026-10-01
    interface: chat.example.com
    ---
    (the reply)

The header is the person's word, not an observation: nothing in a pasted reply
says which weights answered. The reply is kept byte for byte, so its SHA-256
re-derives from the saved file, and everything below it is read from it again.
"""

import datetime
import re
from dataclasses import dataclass
from pathlib import Path

from council_eval.chat_prompt import text_digest

MODEL_KEY = "model"
DATE_KEY = "date"
INTERFACE_KEY = "interface"
HEADER_KEYS = (MODEL_KEY, DATE_KEY, INTERFACE_KEY)
HEADER_END = "---"
KEY_SEPARATOR = ":"
# The BOM a Windows editor may put first is dropped; nothing else is changed.
FILE_ENCODING = "utf-8-sig"
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class RefusedReply(ValueError):
    """A saved reply this import will not take, with the file and the reason."""

    def __init__(self, file: str, reason: str) -> None:
        """Name the file first, so a refusal among thirty-six says which one."""
        super().__init__(f"{file}: {reason}")


@dataclass(frozen=True)
class SavedReply:
    """One saved reply: its file's name, the header's three fields, and the reply itself."""

    file: str
    model: str
    date: str
    interface: str
    reply: str

    @property
    def sha256(self) -> str:
        """Fingerprint the reply, everything below the header, as it was saved."""
        return text_digest(self.reply)


def read_saved_reply(path: Path) -> SavedReply:
    """Read one saved reply, refusing a file whose header is not the three fields asked for."""
    try:
        text = path.read_bytes().decode(FILE_ENCODING)
    except UnicodeDecodeError as fault:
        raise RefusedReply(path.name, f"is not UTF-8 text ({fault})") from fault
    header, reply = split_header(text, path.name)
    fields = header_fields(header, path.name)
    refuse_undated(fields[DATE_KEY], path.name)
    return SavedReply(path.name, fields[MODEL_KEY], fields[DATE_KEY], fields[INTERFACE_KEY], reply)


def split_header(text: str, file: str) -> tuple[list[str], str]:
    """Cut a saved reply at its first `---` line, into the header's lines and the reply."""
    lines = text.splitlines(keepends=True)
    ends = [index for index, line in enumerate(lines) if line.strip() == HEADER_END]
    if not ends:
        raise RefusedReply(file, f"has no {HEADER_END!r} line after its header")
    return lines[: ends[0]], "".join(lines[ends[0] + 1:])


def header_fields(lines: list[str], file: str) -> dict[str, str]:
    """Read the header's `key: value` lines, refusing an unknown, repeated, empty or missing one."""
    fields: dict[str, str] = {}
    for line in filter(str.strip, lines):
        key, separator, value = line.partition(KEY_SEPARATOR)
        key = key.strip()
        if not separator or key not in HEADER_KEYS:
            raise RefusedReply(file, f"header line {line.strip()!r} is none of {HEADER_KEYS}")
        if key in fields:
            raise RefusedReply(file, f"names its {key} twice")
        if not value.strip():
            raise RefusedReply(file, f"leaves its {key} empty")
        fields[key] = value.strip()
    missing = [key for key in HEADER_KEYS if key not in fields]
    if missing:
        raise RefusedReply(file, f"header has no {', '.join(missing)}")
    return fields


def refuse_undated(date: str, file: str) -> None:
    """Refuse a date that is not a real day written YYYY-MM-DD."""
    if not ISO_DATE.fullmatch(date):
        raise RefusedReply(file, f"date {date!r} is not written YYYY-MM-DD")
    try:
        datetime.date.fromisoformat(date)
    except ValueError as fault:
        raise RefusedReply(file, f"date {date!r} is no real day ({fault})") from fault
