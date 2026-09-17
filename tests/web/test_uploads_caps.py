"""How much a run may hold, and the refusal that happens while the bytes arrive.

Bounds rather than an allowlist: evidence may be any bytes, so the protection is
on the way out. Three caps, each refused separately below, and one of them is
enforced in a different place from the other two -- `MAX_UPLOAD_BYTES` cannot be
known before the body is read, so it is the running total that refuses it.

**The cap is enforced while reading, not after.** A cap applied to a buffered
body is not a cap: it admits the whole file into memory first, which is the
thing being prevented. `Content-Length` is the client's claim and the running
total is the fact. That claim cannot be shown through `TestClient` -- it buffers
the request body before the application sees it, so a generator handed to it is
fully drained whatever the server does -- so the last section calls
`uploads._receive` directly, with a stream that counts what was pulled from it.
It is the only place the property lives.

**The two big caps are exercised against a lowered value.** Sending sixteen and
sixty-four megabytes through a test client to prove an arithmetic comparison
would be minutes of the suite's time for nothing; the constants are read at call
time, so lowering one exercises the same code. The shipped numbers are pinned as
literals in the first section, which is what makes a change to them deliberate.
The count cap is small enough to exercise for real, and is.

That lowering is the only patching left in these four files. The directory the
bytes go to used to be patched too and is an argument to `register` now, which
is `test_uploads_destination.py`'s subject.

The whole file skips without the server packages: with no fastapi there is no
endpoint to refuse anything.
"""

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from fastapi import HTTPException                  # noqa: E402

import uploads                                     # noqa: E402

from .upload_fixtures import (                     # noqa: E402
    attach, a_run_to_attach_to, files_under, stored_uploads)

CREATED = 201
REFUSED = 400
TOO_LARGE = 413

# The shipped caps, pinned as literals beside the constants they must equal.
# Imported alone they would agree with themselves, and these are the numbers a
# reader of the README is told the endpoint enforces.
EXPECTED_MAX_UPLOAD_BYTES = 16 * 1024 * 1024
EXPECTED_MAX_UPLOAD_TOTAL_BYTES = 64 * 1024 * 1024
EXPECTED_MAX_UPLOADS_PER_RUN = 20

# Small enough to send in a test, large enough that a chunked read has more than
# one chunk to refuse on.
LOWERED_CAP = 64

# How many chunks the direct stream test offers, and how big each one is, so the
# cap falls in the middle of the body rather than at either end.
STREAM_CHUNK = 16
STREAM_CHUNKS = 40

def bytes_of(count: int) -> bytes:
    """A body of a given length, with no structure the endpoint could react to."""
    return b"e" * count


class CountingStream:
    """A request body that records how much of itself was ever pulled.

    The smallest object `_receive` can read: it calls `request.stream()` and
    iterates it, and nothing else about a request.
    """

    def __init__(self, chunks: int, size: int) -> None:
        """Hold how many chunks are on offer, and count the ones handed over."""
        self.on_offer = chunks
        self.size = size
        self.given = 0

    def stream(self):
        """Hand over one chunk at a time, exactly as a streaming body does."""
        async def chunks():
            """Yield each chunk, counting it as it leaves."""
            for _ in range(self.on_offer):
                self.given += 1
                yield b"s" * self.size

        return chunks()


def receive(stream: CountingStream, written: Path, limit: int) -> dict:
    """Run the streaming read to completion, so a sync test can drive it."""
    return asyncio.run(uploads._receive(stream, written, limit))


# --- the caps the endpoint publishes -------------------------------------------

def test_the_caps_are_the_shipped_numbers() -> None:
    """Pinned as literals, so lowering one in a test below is exercising the real rule."""
    assert uploads.MAX_UPLOAD_BYTES == EXPECTED_MAX_UPLOAD_BYTES
    assert uploads.MAX_UPLOAD_TOTAL_BYTES == EXPECTED_MAX_UPLOAD_TOTAL_BYTES
    assert uploads.MAX_UPLOADS_PER_RUN == EXPECTED_MAX_UPLOADS_PER_RUN


def test_one_file_may_not_be_larger_than_everything_a_run_may_hold() -> None:
    """Guard on the arithmetic: `_room_left` is a `min`, so the wrong order hides one cap."""
    assert uploads.MAX_UPLOAD_BYTES < uploads.MAX_UPLOAD_TOTAL_BYTES


# --- one file that is too large -------------------------------------------------

def test_a_body_over_the_single_file_cap_is_refused(monkeypatch, tmp_path) -> None:
    """413 rather than 400: it is a size, and the reply says how many bytes were allowed."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    monkeypatch.setattr(uploads, "MAX_UPLOAD_BYTES", LOWERED_CAP)
    response = attach(client, content=bytes_of(LOWERED_CAP + 1))
    assert response.status_code == TOO_LARGE
    assert str(LOWERED_CAP) in response.json()["detail"]


def test_a_body_exactly_at_the_cap_is_accepted(monkeypatch, tmp_path) -> None:
    """Non-vacuity: the rule is about the size, not about a body being large."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    monkeypatch.setattr(uploads, "MAX_UPLOAD_BYTES", LOWERED_CAP)
    response = attach(client, content=bytes_of(LOWERED_CAP))
    assert response.status_code == CREATED
    assert response.json()["bytes"] == LOWERED_CAP


def test_a_refused_body_leaves_no_partial_file_behind(monkeypatch, tmp_path) -> None:
    """The bytes were already being written when the cap was reached; they are removed."""
    client, _, root = a_run_to_attach_to(tmp_path)
    monkeypatch.setattr(uploads, "MAX_UPLOAD_BYTES", LOWERED_CAP)
    attach(client, content=bytes_of(LOWERED_CAP + 1))
    assert files_under(root) == []


def test_a_refused_body_is_not_recorded_on_the_run(monkeypatch, tmp_path) -> None:
    """The other half of the same rollback: no record of a file that was not kept."""
    client, registry, _ = a_run_to_attach_to(tmp_path)
    monkeypatch.setattr(uploads, "MAX_UPLOAD_BYTES", LOWERED_CAP)
    attach(client, content=bytes_of(LOWERED_CAP + 1))
    assert stored_uploads(registry) == []


# --- everything one run may hold -------------------------------------------------

def test_a_file_that_would_take_the_run_over_its_total_is_refused(monkeypatch,
                                                                   tmp_path) -> None:
    """The second cap: one file within the per-file limit can still be one too many."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    monkeypatch.setattr(uploads, "MAX_UPLOAD_TOTAL_BYTES", LOWERED_CAP)
    assert attach(client, content=bytes_of(LOWERED_CAP - 1)).status_code == CREATED
    assert attach(client, content=bytes_of(2)).status_code == TOO_LARGE


def test_a_run_already_at_its_total_is_refused_before_a_byte_is_read(monkeypatch,
                                                                     tmp_path) -> None:
    """Refused by `_check_room`, whose sentence names the total rather than what was left."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    monkeypatch.setattr(uploads, "MAX_UPLOAD_TOTAL_BYTES", LOWERED_CAP)
    attach(client, content=bytes_of(LOWERED_CAP))
    response = attach(client, content=bytes_of(1))
    assert response.status_code == TOO_LARGE
    assert str(LOWERED_CAP) in response.json()["detail"]


def test_a_run_under_its_total_still_accepts_another_file(monkeypatch, tmp_path) -> None:
    """Non-vacuity for both: the total is what refuses, not the second attach."""
    client, registry, _ = a_run_to_attach_to(tmp_path)
    monkeypatch.setattr(uploads, "MAX_UPLOAD_TOTAL_BYTES", LOWERED_CAP)
    attach(client, content=bytes_of(1))
    attach(client, content=bytes_of(1))
    assert len(stored_uploads(registry)) == 2


# --- how many files one run may hold ---------------------------------------------

def test_a_run_stops_accepting_files_at_the_count_cap(monkeypatch, tmp_path) -> None:
    """The shipped number, exercised for real: twenty land and the twenty-first does not."""
    client, registry, _ = a_run_to_attach_to(tmp_path)
    for index in range(uploads.MAX_UPLOADS_PER_RUN):
        assert attach(client, content=bytes_of(1), name=f"note-{index}").status_code == CREATED
    response = attach(client, content=bytes_of(1), name="one too many")
    assert response.status_code == REFUSED
    assert str(uploads.MAX_UPLOADS_PER_RUN) in response.json()["detail"]
    assert len(stored_uploads(registry)) == uploads.MAX_UPLOADS_PER_RUN


# --- the cap is applied while reading --------------------------------------------

def test_the_stream_is_not_drained_once_the_cap_is_passed(tmp_path) -> None:
    """A cap applied after buffering is not a cap, and this is the only place that shows.

    Driven against `_receive` rather than through the endpoint because
    `TestClient` buffers the request body before the application sees it: a
    generator handed to it is fully consumed whatever the server does, so the
    same test through HTTP would pass with the streaming removed.
    """
    stream = CountingStream(STREAM_CHUNKS, STREAM_CHUNK)
    with pytest.raises(HTTPException) as refused:
        receive(stream, tmp_path / "partial", LOWERED_CAP)
    assert refused.value.status_code == TOO_LARGE
    assert stream.given < STREAM_CHUNKS


def test_the_stream_is_drained_when_the_body_fits(tmp_path) -> None:
    """Non-vacuity: a reader that stopped after one chunk would satisfy the test above."""
    stream = CountingStream(STREAM_CHUNKS, STREAM_CHUNK)
    held = receive(stream, tmp_path / "whole", STREAM_CHUNKS * STREAM_CHUNK)
    assert stream.given == STREAM_CHUNKS
    assert held["bytes"] == STREAM_CHUNKS * STREAM_CHUNK


def test_the_partial_file_is_gone_when_the_stream_is_cut_off(tmp_path) -> None:
    """The chunks already written are removed, so a rejected upload leaves nothing behind."""
    partial = tmp_path / "partial"
    with pytest.raises(HTTPException):
        receive(CountingStream(STREAM_CHUNKS, STREAM_CHUNK), partial, LOWERED_CAP)
    assert not partial.exists()
