"""Guards on a server that answers but not in HTTP: unavailable with a reason, for both calls."""

import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterator

import pytest

from council import transport
from council.transport import ModelUnavailable, get_json, post_json

PAYLOAD = {"model": "qwen2.5:7b-instruct", "prompt": "hello"}
TIMEOUT_SECONDS = 5.0
# What a server that is not speaking HTTP sends, and one that stops mid-body.
NOT_A_STATUS_LINE = b"garbage\r\n"
CUT_OFF_BODY = b"HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\n{}"
# Nothing at all: the server hung up before answering.
NO_REPLY = b""
# How often the server looks for a shutdown, so each test does not wait half a second.
POLL_SECONDS = 0.01

CALLS = {
    "post": lambda url: post_json(url, PAYLOAD, timeout=TIMEOUT_SECONDS),
    "get": lambda url: get_json(url, timeout=TIMEOUT_SECONDS),
}


def replying_with(raw: bytes) -> type[BaseHTTPRequestHandler]:
    """Build a handler that reads the request and sends these bytes back, not an HTTP reply."""

    class Raw(BaseHTTPRequestHandler):
        """A server that writes what it is given and hangs up."""

        def do_GET(self) -> None:
            """Answer a read with the raw bytes."""
            self.wfile.write(raw)

        def do_POST(self) -> None:
            """Take the whole request body first, so the client is not cut off sending it."""
            self.rfile.read(int(self.headers["Content-Length"]))
            self.wfile.write(raw)

        def log_message(self, *_) -> None:
            """Keep the test's output quiet."""

    return Raw


@contextmanager
def serving(raw: bytes) -> Iterator[str]:
    """Serve these raw bytes on a free loopback port for as long as a test needs it."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), replying_with(raw))
    poll = {"poll_interval": POLL_SECONDS}
    threading.Thread(target=server.serve_forever, kwargs=poll, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api/generate"
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize("call", sorted(CALLS))
@pytest.mark.parametrize(
    ("raw", "named"),
    [(NOT_A_STATUS_LINE, "BadStatusLine"), (CUT_OFF_BODY, "IncompleteRead")],
    ids=["bad-status-line", "incomplete-read"],
)
def test_a_reply_that_is_not_well_formed_http_is_unavailable_and_says_how(call, raw, named):
    with serving(raw) as url, pytest.raises(ModelUnavailable, match=f"malformed HTTP reply: {named}"):
        CALLS[call](url)


@pytest.mark.parametrize("call", sorted(CALLS))
def test_a_server_that_hangs_up_unanswered_is_still_named_as_not_reached(call):
    # RemoteDisconnected is an HTTPException and an OSError, and reads as the second.
    with serving(NO_REPLY) as url, pytest.raises(ModelUnavailable, match="could not be reached"):
        CALLS[call](url)


def failing_as_a_bug(request, timeout=None):
    """Fail as a programming error does, which no server fault is."""
    raise TypeError("a bug, not the server")


@pytest.mark.parametrize("call", sorted(CALLS))
def test_a_fault_that_is_not_the_server_s_is_not_mistaken_for_one(monkeypatch, call):
    monkeypatch.setattr(transport.NO_PROXY_OPENER, "open", failing_as_a_bug)
    with pytest.raises(TypeError, match="a bug, not the server"):
        CALLS[call]("http://127.0.0.1:11434/api/generate")
