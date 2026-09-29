"""Guards on the one place the council opens a socket: no proxy, and loud failures."""

import io
import json
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterator

import pytest

import model_shapes as shapes
from council import transport
from council.settings import Settings
from council.transport import (
    JSON_CONTENT_TYPE,
    ModelUnavailable,
    build_request,
    post_json,
    read_json,
)

URL = "http://127.0.0.1:11434/api/generate"
PAYLOAD = {"model": "qwen2.5:7b-instruct", "prompt": "hello"}
# A server that takes a second, and a caller that waits a fifth of one.
SLOW_SECONDS = 1.0
PATIENCE_SECONDS = 0.2


class Answered:
    """A response object in the shape urllib hands back, without a socket."""

    def __init__(self, body: str) -> None:
        """Hold the body this fake response will give up."""
        self.body = body

    def __enter__(self) -> "Answered":
        """Enter the context `post_json` opens the response in."""
        return self

    def __exit__(self, *_) -> bool:
        """Leave it, suppressing nothing."""
        return False

    def read(self) -> bytes:
        """Give the body as urllib would, in bytes."""
        return self.body.encode("utf-8")


def answering(body: str):
    """Build an opener stand-in that answers every request with one body."""
    return lambda request, timeout=None: Answered(body)


def raising(fault: Exception):
    """Build an opener stand-in that fails the way a real one fails."""

    def refuse(request, timeout=None):
        """Fail the way a server that is not there fails."""
        raise fault

    return refuse


def proxy_handlers(opener: urllib.request.OpenerDirector) -> list:
    """Give the handlers of an opener that would route a request through a proxy."""
    return [
        handler
        for handler in opener.handlers
        if isinstance(handler, urllib.request.ProxyHandler) and handler.proxies
    ]


def test_the_transport_never_goes_through_a_proxy(monkeypatch):
    # The 502 trap on this machine: urllib would send a request for 127.0.0.1 to
    # the corporate proxy, and the failure reads exactly like Ollama being down.
    # An empty ProxyHandler leaves the opener holding no proxy handler at all.
    monkeypatch.setenv("http_proxy", "http://proxy.invalid:8080")
    assert proxy_handlers(transport.NO_PROXY_OPENER) == []


def test_an_ordinary_opener_is_what_would_have_gone_through_it(monkeypatch):
    # The other half of the guard: without the bypass, this is what happens.
    monkeypatch.setenv("http_proxy", "http://proxy.invalid:8080")
    assert proxy_handlers(urllib.request.build_opener()) != []


def test_a_request_is_a_json_post():
    request = build_request(URL, PAYLOAD)
    assert request.method == "POST"
    assert request.headers["Content-type"] == JSON_CONTENT_TYPE
    assert json.loads(request.data.decode("utf-8")) == PAYLOAD


def test_a_reply_comes_back_parsed(monkeypatch):
    monkeypatch.setattr(transport.NO_PROXY_OPENER, "open", answering('{"response": "hi"}'))
    assert post_json(URL, PAYLOAD) == {"response": "hi"}


def test_a_server_that_is_not_there_is_reported_as_unavailable(monkeypatch):
    fault = urllib.error.URLError("Connection refused")
    monkeypatch.setattr(transport.NO_PROXY_OPENER, "open", raising(fault))
    with pytest.raises(ModelUnavailable, match="could not be reached"):
        post_json(URL, PAYLOAD)


def test_a_refused_request_quotes_what_the_server_said(monkeypatch):
    fault = urllib.error.HTTPError(URL, 404, "Not Found", {}, None)
    monkeypatch.setattr(transport.NO_PROXY_OPENER, "open", raising(fault))
    with pytest.raises(ModelUnavailable, match="answered 404"):
        post_json(URL, PAYLOAD)


def test_a_proxy_answering_html_is_not_mistaken_for_a_model(monkeypatch):
    # What the 502 actually looks like when it arrives: a page, not an envelope.
    monkeypatch.setattr(transport.NO_PROXY_OPENER, "open", answering("<html>502</html>"))
    with pytest.raises(ModelUnavailable, match="did not return JSON"):
        post_json(URL, PAYLOAD)


def test_a_body_that_is_not_json_is_refused_with_an_excerpt():
    with pytest.raises(ModelUnavailable, match="not json either"):
        read_json(URL, "not json either")


@pytest.mark.parametrize("shape", sorted(shapes.REFUSED))
def test_a_model_that_cannot_do_what_was_asked_fails_in_the_server_s_own_words(monkeypatch, shape):
    # Recorded: what Ollama 0.34.3 answered a model that cannot generate, and a
    # `think` the model does not support.
    refused = shapes.REFUSED[shape]
    body = io.BytesIO(refused["body"].encode("utf-8"))
    fault = urllib.error.HTTPError(URL, refused["status"], "Bad Request", {}, body)
    monkeypatch.setattr(transport.NO_PROXY_OPENER, "open", raising(fault))
    words = json.loads(refused["body"])["error"].split('" ', 1)[1]
    with pytest.raises(ModelUnavailable, match=f"answered 400: .*{words}"):
        post_json(URL, PAYLOAD)


class Slow(BaseHTTPRequestHandler):
    """A server that takes longer to answer than the caller will wait."""

    def do_POST(self) -> None:
        """Answer late, as a model too big for the machine does."""
        time.sleep(SLOW_SECONDS)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *_) -> None:
        """Keep the test's output quiet."""


@contextmanager
def slow_server() -> Iterator[str]:
    """Serve slowly on a free loopback port for as long as a test needs it."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), Slow)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api/generate"
    finally:
        server.shutdown()
        server.server_close()


def test_a_server_slower_than_the_timeout_is_named_as_slow_and_not_as_absent():
    with slow_server() as url, pytest.raises(ModelUnavailable, match="did not answer within 0.2 s"):
        post_json(url, PAYLOAD, timeout=PATIENCE_SECONDS)


def test_with_no_timeout_given_the_operator_s_setting_is_what_is_waited(monkeypatch):
    patient = Settings("any:1b", "http://127.0.0.1:11434", PATIENCE_SECONDS, 8192)
    monkeypatch.setattr(transport, "current_settings", lambda: patient)
    with slow_server() as url, pytest.raises(ModelUnavailable, match="did not answer within 0.2 s"):
        post_json(url, PAYLOAD)


def test_a_connection_that_timed_out_is_named_as_slow_too(monkeypatch):
    fault = urllib.error.URLError(TimeoutError("timed out"))
    monkeypatch.setattr(transport.NO_PROXY_OPENER, "open", raising(fault))
    with pytest.raises(ModelUnavailable, match="did not answer within 180 s"):
        post_json(URL, PAYLOAD)
