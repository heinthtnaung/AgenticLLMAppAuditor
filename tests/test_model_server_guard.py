"""Guards on the suite itself: a request to the model server, or any machine but this one, fails.

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


def test_a_request_to_another_machine_is_refused_whatever_its_port():
    # A documentation address (RFC 5737): were the guard gone, nothing would answer.
    with pytest.raises(AssertionError, match="give it a fake client"):
        post_json("http://192.0.2.1:8080/api/generate", {}, timeout=0.2)


def test_the_server_elsewhere_a_test_opts_in_to_is_refused_as_this_machine_s_is(remote_server):
    with pytest.raises(AssertionError, match="give it a fake client"):
        transport.NO_PROXY_OPENER.open(f"{remote_server}/api/version", timeout=0.2)
    assert settings.current_settings().server == remote_server


def test_the_opted_in_server_is_gone_once_the_test_that_asked_for_it_ends():
    # Runs after the test above: the cached settings are read again, from a clean environment.
    assert settings.current_settings().server == "http://127.0.0.1:11434"
