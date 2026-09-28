"""Guards on the suite itself: a request to the model server fails the test that sends it.

`tests/conftest.py` refuses it before any socket is opened, so this asks no model.
"""

import socket
import urllib.error

import pytest

from council import settings, transport
from council.transport import post_json


def test_a_request_to_the_model_server_fails_the_test_that_sent_it():
    server = settings.current_settings().server
    with pytest.raises(AssertionError, match="give it a fake client"):
        post_json(f"{server}/api/generate", {}, timeout=0.2)


def a_port_nothing_listens_on() -> int:
    """Give a loopback port that was free a moment ago, so a request to it is refused by the OS."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_a_plain_url_to_the_model_server_is_refused_as_a_request_is():
    server = settings.current_settings().server
    with pytest.raises(AssertionError, match="give it a fake client"):
        transport.NO_PROXY_OPENER.open(f"{server}/api/version", timeout=0.2)


def test_a_plain_url_to_another_port_is_passed_through_to_the_opener():
    # Refused by the operating system, not by the guard: nothing listens there.
    elsewhere = f"http://127.0.0.1:{a_port_nothing_listens_on()}/"
    with pytest.raises(urllib.error.URLError):
        transport.NO_PROXY_OPENER.open(elsewhere, timeout=0.2)
