"""The auditor makes no network calls: the project's central safety boundary.

Audited source is often proprietary, so the guarantee that it never leaves the
machine is the reason the tool can be pointed at a private repository at all.
It is asserted here rather than assumed, because a stray import could break it
silently.
"""

import socket

import pytest
from conftest import CORPUS_APPS, CORPUS_DIR, require_corpus
from parsing.extractor import extract_repo
from artifacts.surface import surfaces_to_json


class NoNetwork(socket.socket):
    """A socket that refuses to connect, recording any attempt."""

    attempts: list = []

    def connect(self, address):
        """Record the address and refuse, so a test can see what was tried."""
        NoNetwork.attempts.append(address)
        raise OSError(f"network blocked by test: {address}")


@pytest.fixture
def no_network(monkeypatch):
    """Replace the socket type so any outbound connection fails and is recorded."""
    NoNetwork.attempts = []
    monkeypatch.setattr(socket, "socket", NoNetwork)
    return NoNetwork


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_extracting_a_repository_touches_no_network(app: str, no_network) -> None:
    """A full extraction completes with sockets blocked, and attempts none."""
    require_corpus(app)
    surfaces = extract_repo(str(CORPUS_DIR / app))
    assert surfaces, "extraction produced nothing, so this proves little"
    assert no_network.attempts == []


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_serialising_the_artifact_touches_no_network(app: str, no_network) -> None:
    """Writing the artifact is local too: nothing is reported to anywhere."""
    require_corpus(app)
    surfaces_to_json(extract_repo(str(CORPUS_DIR / app)))
    assert no_network.attempts == []
