"""The auditor makes no network calls: the project's central safety boundary.

Audited source is often proprietary, so the guarantee that it never leaves the
machine is the reason the tool can be pointed at a private repository at all.
It is asserted here rather than assumed, because a stray import could break it
silently.
"""

import socket

import pytest
from deps import syft_runner
from artifacts.aibom import build_aibom
from conftest import CORPUS_APPS, CORPUS_DIR, require_corpus, scan_to_json
from parsing.extractor import extract_repo
from artifacts.mapping import build_mapping
from dependency_fixtures import corpus_sbom
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
    surfaces = extract_repo(str(CORPUS_DIR / app)).surfaces
    assert surfaces, "extraction produced nothing, so this proves little"
    assert no_network.attempts == []


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_serialising_the_artifact_touches_no_network(app: str, no_network) -> None:
    """Writing the artifact is local too: nothing is reported to anywhere."""
    require_corpus(app)
    scan_to_json(str(CORPUS_DIR / app))
    assert no_network.attempts == []


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_building_the_aibom_touches_no_network(app: str, no_network) -> None:
    """The AIBOM is derived from surfaces already in memory: nothing is looked up."""
    require_corpus(app)
    surfaces = extract_repo(str(CORPUS_DIR / app)).surfaces
    assert surfaces, "extraction produced nothing, so this proves little"
    build_aibom(surfaces)
    assert no_network.attempts == []


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_building_the_mapping_touches_no_network(app: str, no_network) -> None:
    """The import-to-package join is decided from local tables, never a package index."""
    require_corpus(app)
    surfaces = extract_repo(str(CORPUS_DIR / app)).surfaces
    assert build_mapping(surfaces, corpus_sbom())["surface_count"] == len(surfaces)
    assert no_network.attempts == []


def test_the_sbom_generator_is_told_not_to_phone_home() -> None:
    """Syft runs in its own process, so its update check is disabled by environment.

    A blocked socket in this process would prove nothing about a subprocess;
    this setting is what actually keeps the SBOM step offline.
    """
    assert syft_runner.SYFT_ENV["SYFT_CHECK_FOR_APP_UPDATE"] == "false"
