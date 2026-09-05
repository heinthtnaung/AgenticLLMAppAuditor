"""A socket type that refuses every connection, shared by the two offline test files.

`tests/parsing/test_offline.py` holds the offline guarantee for the audit path
and `tests/retrieval/test_store_offline.py` holds it for the knowledge store.
Both assert the same way -- perform a real operation with every outbound
connection refused, then assert that none was attempted -- so the refusing
socket and the fixture that installs it live here rather than in one of them
with a copy in the other.
"""

import socket

import pytest


class NoNetwork(socket.socket):
    """A socket that refuses to connect, recording any attempt."""

    attempts: list = []

    def connect(self, address) -> None:
        """Record the address and refuse, so a test can see what was tried."""
        NoNetwork.attempts.append(address)
        raise OSError(f"network blocked by test: {address}")


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> type[NoNetwork]:
    """Replace the socket type so any outbound connection fails and is recorded."""
    NoNetwork.attempts = []
    monkeypatch.setattr(socket, "socket", NoNetwork)
    return NoNetwork
