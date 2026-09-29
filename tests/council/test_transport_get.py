"""Guards on reading from the model server: the same opener, the same loud failures, a plain URL."""

import io
import urllib.error

import pytest

from council import transport
from council.transport import ModelUnavailable, get_json

URL = "http://127.0.0.1:11434/api/version"


def answering(body: str, asked: list):
    """Build an opener stand-in that notes what it was asked and answers with one body."""

    def opened(request, timeout=None):
        """Note the request and its timeout, and answer it."""
        asked.append((request, timeout))
        return io.BytesIO(body.encode("utf-8"))

    return opened


def test_a_read_goes_through_the_no_proxy_opener_as_a_plain_url_parsed(monkeypatch):
    asked = []
    reply = answering('{"version": "0.34.3"}', asked)
    monkeypatch.setattr(transport.NO_PROXY_OPENER, "open", reply)
    assert get_json(URL, timeout=5) == {"version": "0.34.3"}
    assert asked == [(URL, 5)]


def test_a_server_that_is_not_there_is_reported_as_unavailable(monkeypatch):
    def refused(request, timeout=None):
        """Fail as a closed port fails."""
        raise urllib.error.URLError("Connection refused")

    monkeypatch.setattr(transport.NO_PROXY_OPENER, "open", refused)
    with pytest.raises(ModelUnavailable, match="could not be reached"):
        get_json(URL, timeout=5)


def test_a_reply_that_is_not_json_is_refused(monkeypatch):
    monkeypatch.setattr(transport.NO_PROXY_OPENER, "open", answering("<html>502</html>", []))
    with pytest.raises(ModelUnavailable, match="did not return JSON"):
        get_json(URL, timeout=5)
