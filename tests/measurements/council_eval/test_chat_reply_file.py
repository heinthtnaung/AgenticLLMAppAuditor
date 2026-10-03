"""Guards on a saved reply's file: the person's three header fields, and the reply byte for byte."""

from hashlib import sha256

import pytest

import chat_samples
from council_eval.chat_reply_file import RefusedReply, read_saved_reply

REPLY = "Some prose.\r\n```json\r\n{}\r\n```\r\n"


def saved(tmp_path, text: str, encoding: str = "utf-8"):
    """Save a reply file and read it back."""
    path = tmp_path / "reply.txt"
    path.write_bytes(text.encode(encoding))
    return read_saved_reply(path)


def test_the_header_s_fields_are_kept_as_typed_and_the_reply_byte_for_byte(tmp_path):
    header = "model:  Some Model 9 (Thinking, extended)  \ndate: 2026-10-01\ninterface: web\n---\n"
    read = saved(tmp_path, header + REPLY)
    assert (read.model, read.date, read.interface) == (
        "Some Model 9 (Thinking, extended)", "2026-10-01", "web"
    )
    assert read.reply == REPLY
    assert read.sha256 == sha256(REPLY.encode("utf-8")).hexdigest()
    assert read.file == "reply.txt"


def test_a_markdown_rule_inside_the_reply_stays_in_the_reply(tmp_path):
    # The header ends at its first `---`; one the chat wrote below it is the chat's.
    reply = "Assessment.\n---\n```json\n{}\n```\n---\nDone.\n"
    assert saved(tmp_path, chat_samples.HEADER + reply).reply == reply


def test_a_header_saved_with_windows_line_endings_is_read_the_same(tmp_path):
    header = chat_samples.HEADER.replace("\n", "\r\n")
    read = saved(tmp_path, header + REPLY)
    assert (read.model, read.date, read.interface) == (
        chat_samples.FIXTURE_MODEL, "2026-10-01", chat_samples.FIXTURE_INTERFACE
    )
    assert read.reply == REPLY


def test_a_byte_order_mark_a_windows_editor_adds_is_dropped(tmp_path):
    read = saved(tmp_path, chat_samples.HEADER + REPLY, encoding="utf-8-sig")
    assert read.model == chat_samples.FIXTURE_MODEL


def test_the_fixtures_read_as_a_person_would_save_them():
    read = read_saved_reply(chat_samples.FORWARD_FIXTURE)
    assert read.model == chat_samples.FIXTURE_MODEL
    assert read.reply.startswith("Here is my assessment")


@pytest.mark.parametrize(
    "header, reason",
    [
        ("model: m\ndate: 2026-10-01\ninterface: web\n", "has no '---' line"),
        ("model: m\ndate: 2026-10-01\ninterface: web\nseed: 1\n---\n", "is none of"),
        ("model m\ndate: 2026-10-01\ninterface: web\n---\n", "is none of"),
        ("model: m\nmodel: n\ndate: 2026-10-01\ninterface: web\n---\n", "names its model twice"),
        ("model: \ndate: 2026-10-01\ninterface: web\n---\n", "leaves its model empty"),
        ("model: m\ndate: 2026-10-01\n---\n", "header has no interface"),
        ("model: m\ndate: 1 Oct 2026\ninterface: web\n---\n", "is not written YYYY-MM-DD"),
        ("model: m\ndate: 2026-02-30\ninterface: web\n---\n", "is no real day"),
    ],
    ids=["no end", "unknown key", "no colon", "twice", "empty", "missing", "format", "no day"],
)
def test_a_header_that_is_not_the_three_fields_is_refused_naming_the_file(tmp_path, header, reason):
    with pytest.raises(RefusedReply, match=f"^reply.txt: .*{reason}"):
        saved(tmp_path, header + REPLY)


def test_a_file_that_is_not_utf_8_is_refused_naming_the_file(tmp_path):
    with pytest.raises(RefusedReply, match="^reply.txt: is not UTF-8 text"):
        saved(tmp_path, chat_samples.HEADER + "caf\xe9", encoding="latin-1")
