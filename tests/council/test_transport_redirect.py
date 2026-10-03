"""Guards on a server that redirects: never followed, for both calls, and said where it pointed.

Two real servers on loopback, each on a port the system chose: one answers
every request with a redirect to the other, and both keep a log of what they
were asked, so a redirect followed shows as a second request.
"""

import re
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterator

import pytest

from council.transport import ModelUnavailable, get_json, post_json

PAYLOAD = {"model": "qwen2.5:7b-instruct", "prompt": "the advisory text"}
TIMEOUT_SECONDS = 5.0
# How often a server looks for a shutdown, so each test does not wait half a second.
POLL_SECONDS = 0.01
REDIRECTS = (301, 302, 303, 307, 308)
PATH = "/api/generate"

CALLS = {
    "post": lambda url: post_json(url, PAYLOAD, timeout=TIMEOUT_SECONDS),
    "get": lambda url: get_json(url, timeout=TIMEOUT_SECONDS),
}


def logging_handler(log: list, code: int, location: str) -> type[BaseHTTPRequestHandler]:
    """Build a handler that notes each request, then answers it with this status and location."""

    class Logged(BaseHTTPRequestHandler):
        """A server that answers everything the same way and remembers what it was asked."""

        def answer(self) -> None:
            """Read any body, note the request, and send the status with an empty body."""
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            log.append((self.command, self.path))
            self.send_response(code)
            if location:
                self.send_header("Location", location)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")

        do_GET = answer
        do_POST = answer

        def log_message(self, *_) -> None:
            """Keep the test's output quiet."""

    return Logged


@contextmanager
def serving(log: list, code: int, location: str = "") -> Iterator[str]:
    """Serve one status on a free loopback port for as long as a test needs it, giving its URL."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), logging_handler(log, code, location))
    poll = {"poll_interval": POLL_SECONDS}
    threading.Thread(target=server.serve_forever, kwargs=poll, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize("call", sorted(CALLS))
@pytest.mark.parametrize("code", REDIRECTS)
def test_a_redirect_is_refused_and_nothing_is_asked_where_it_points(call, code):
    asked, elsewhere_asked = [], []
    with serving(elsewhere_asked, 200) as elsewhere:
        target = f"{elsewhere}{PATH}"
        with serving(asked, code, target) as server:
            said = f"{server}{PATH} answered {code}, a redirect to {target}, which is not followed"
            with pytest.raises(ModelUnavailable, match=re.escape(said)):
                CALLS[call](f"{server}{PATH}")
    assert asked == [("POST" if call == "post" else "GET", PATH)]
    assert elsewhere_asked == []


def test_a_redirect_that_names_no_location_says_so():
    with serving([], 302) as server:
        with pytest.raises(ModelUnavailable, match="a redirect to no location"):
            get_json(f"{server}{PATH}", timeout=TIMEOUT_SECONDS)


def test_a_server_that_answers_itself_is_still_read():
    asked = []
    with serving(asked, 200) as server:
        assert get_json(f"{server}{PATH}", timeout=TIMEOUT_SECONDS) == {}
    assert asked == [("GET", PATH)]
