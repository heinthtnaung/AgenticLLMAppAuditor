"""A file of the audited tree this process cannot open.

An audited tree is somebody else's checkout: a file with no read permission is
an ordinary thing to find in one, reached by nothing more exotic than an archive
restored without its modes. `_read` caught `UnicodeDecodeError` and not
`OSError`, so a `chmod 000` file was a **500** while the non-UTF-8 file next to
it was a named 400 -- the same fault, one `except` clause apart, and the third
time this project has found that exact pair.

**Both messages are asserted, and that they differ.** The status is 400 either
way, so the sentence is the only thing telling a reader whether to `chmod` a
file or to stop asking a binary for a line of source. `baselines/static_rules.py`
already catches both for the same kind of file, which is what makes this a gap
rather than a decision.

`held.stat()` moved inside the same `try`. That half is belt and braces and is
not reachable from here: `_inside` calls `is_file()` first, which swallows the
`OSError` a stat would raise and answers "not a file of this run's audited
tree". The reachable fault is the read, and it is what is driven below.

The hand-editable files this project *owns* -- a drafted key, either manifest --
are `test_unopenable_files.py`, through two other guarded readers. The rest of
what this route refuses is `test_source_refusals.py`; the constants for the
non-UTF-8 file are spelled again here rather than imported from it, because the
claim is that the two sentences are different and a comparison has to hold both.

`locked_file.locked` attempts the read before any test goes on and skips if it
succeeded, so this cannot pass as root by reading a file it called unreadable.
Nothing here reads a repository this project does not own: `source_fixtures`
writes the tree into `tmp_path` and points the download root there first.
"""

import errno
import os
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from fastapi.testclient import TestClient                     # noqa: E402

from locked_file import locked                                # noqa: E402

from .source_fixtures import (                                # noqa: E402
    NO_SOURCE, OK, REFUSED, SOURCE_FILE, SOURCE_LINES, a_client_and_its_tree,
    ask_for_source, refusal_from)

# The line asked for. Inside the file, so a refusal is about the file and never
# about the line.
A_REAL_LINE = 5

# A file that is not text at all, planted beside the locked one. The first byte
# pair is invalid UTF-8, which is what `read_text` raises on.
NOT_TEXT_FILE = "logo.bin"
NOT_TEXT_BYTES = b"\xff\xfe\x00binary, not source\x00"

# The two sentences, which have to stay different: one says fix the mode, the
# other says this is not source.
CANNOT_OPEN_SAID = "cannot be read"
NOT_UTF8_SAID = "is not UTF-8 text"

# What the operating system calls a read denied by the mode, asked of the
# operating system rather than spelled: the claim is that the reason is carried
# through, not that this machine words it a given way.
DENIED = os.strerror(errno.EACCES)


def a_client_over_a_locked_file(monkeypatch: pytest.MonkeyPatch,
                                tmp_path: Path) -> TestClient:
    """A client over the ordinary tree, with its one source file unopenable."""
    client, tree = a_client_and_its_tree(monkeypatch, tmp_path)
    locked(tree / SOURCE_FILE)
    return client


def a_client_over_a_binary(monkeypatch: pytest.MonkeyPatch,
                           tmp_path: Path) -> TestClient:
    """A client over the ordinary tree, with a file in it that is not text."""
    client, tree = a_client_and_its_tree(monkeypatch, tmp_path)
    (tree / NOT_TEXT_FILE).write_bytes(NOT_TEXT_BYTES)
    return client


# --- the file nobody can open ----------------------------------------------------

def test_a_file_this_process_cannot_open_is_refused_rather_than_crashed_on(
        monkeypatch, tmp_path) -> None:
    """A 400 with a sentence, where an `OSError` used to reach the log as a 500."""
    client = a_client_over_a_locked_file(monkeypatch, tmp_path)
    assert CANNOT_OPEN_SAID in refusal_from(
        ask_for_source(client, SOURCE_FILE, A_REAL_LINE), REFUSED)


def test_the_refusal_names_the_file_and_the_reason_the_open_failed(monkeypatch,
                                                                   tmp_path) -> None:
    """Non-vacuity: "cannot be read" alone would not tell a reader to `chmod` anything."""
    client = a_client_over_a_locked_file(monkeypatch, tmp_path)
    detail = refusal_from(ask_for_source(client, SOURCE_FILE, A_REAL_LINE), REFUSED)
    assert SOURCE_FILE in detail
    assert DENIED in detail


def test_a_locked_file_is_not_answered_as_a_missing_one(monkeypatch, tmp_path) -> None:
    """The distinction the status carries: the file is there, and its mode is the problem."""
    client = a_client_over_a_locked_file(monkeypatch, tmp_path)
    assert ask_for_source(client, SOURCE_FILE, A_REAL_LINE).status_code != NO_SOURCE


# --- and the file beside it that is not text -------------------------------------

def test_a_file_that_is_not_utf8_keeps_its_own_sentence(monkeypatch, tmp_path) -> None:
    """The refusal that already worked must not have been generalised away."""
    client = a_client_over_a_binary(monkeypatch, tmp_path)
    assert NOT_UTF8_SAID in refusal_from(
        ask_for_source(client, NOT_TEXT_FILE, A_REAL_LINE), REFUSED)


def test_the_two_refusals_do_not_say_the_same_thing(monkeypatch, tmp_path) -> None:
    """Same status, two different repairs: `chmod` the file, or stop asking for it.

    One message for both would be true and useless, which is the state the
    narrower `except` clause was one line away from producing.
    """
    client, tree = a_client_and_its_tree(monkeypatch, tmp_path)
    (tree / NOT_TEXT_FILE).write_bytes(NOT_TEXT_BYTES)
    locked(tree / SOURCE_FILE)
    unopenable = refusal_from(ask_for_source(client, SOURCE_FILE, A_REAL_LINE), REFUSED)
    not_text = refusal_from(ask_for_source(client, NOT_TEXT_FILE, A_REAL_LINE), REFUSED)
    assert NOT_UTF8_SAID not in unopenable
    assert DENIED not in not_text


# --- the off position -------------------------------------------------------------

def test_a_readable_file_in_the_same_tree_still_answers_its_window(monkeypatch,
                                                                   tmp_path) -> None:
    """Without it, a route that refused every file would satisfy everything above."""
    client, _tree = a_client_and_its_tree(monkeypatch, tmp_path)
    response = ask_for_source(client, SOURCE_FILE, A_REAL_LINE)
    assert response.status_code == OK, response.text
    window = response.json()
    assert window["lines"][window["line"] - window["first_line"]] == SOURCE_LINES[A_REAL_LINE - 1]
