"""The auditor makes no network calls: the project's central safety boundary.

Audited source is often proprietary, so the guarantee that it never leaves the
machine is the reason the tool can be pointed at a private repository at all.
It is asserted here rather than assumed, because a stray import could break it
silently.

The audit workflow is the part of the tool that most threatens the guarantee.
LangGraph brings in `langsmith`, whose tracing uploads every node's input and
output -- which here means the audited repository's paths, file names and code
identifiers. The workflow module opts out of it at import time, and the last
tests below hold that opt-out to the guarantee rather than to a default.
"""

import importlib.util
import os
import socket

import pytest
from checks import workflow
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK
from deps import syft_runner
from artifacts.aibom import build_aibom
from conftest import CORPUS_APPS, CORPUS_DIR, SRC_DIR, require_corpus, scan_to_json
from parsing.extractor import extract_repo
from artifacts.mapping import build_mapping
from dependency_fixtures import SUPPORT_AGENT, corpus_sbom
from findings_fixtures import corpus_inputs
from artifacts.surface import surfaces_to_json

# The checks the workflow plans for a Python app: the widest path through it.
PYTHON_APP_PLAN = [PERMISSION_CHECK, SUPPLY_CHAIN_CHECK, TAINT_CHECK]

# What that app really yields, so a silent run cannot pass this file.
SUPPORT_AGENT_FINDINGS = 2

WORKFLOW_SOURCE = SRC_DIR / "checks" / "workflow.py"

# The two settings that would send a trace of the audit to LangSmith.
TRACING_VARIABLES = ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2")


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


def test_compiling_the_audit_graph_touches_no_network(no_network) -> None:
    """Building the loop is local: the framework looks nothing up as it wires it."""
    assert workflow.build_graph() is not None
    assert no_network.attempts == []


def test_running_the_whole_audit_workflow_touches_no_network(no_network) -> None:
    """Every check the planner can run, over a real app, with every socket refused."""
    require_corpus(SUPPORT_AGENT)
    state = workflow.audit(*corpus_inputs(SUPPORT_AGENT, corpus_sbom()), PYTHON_APP_PLAN)
    assert len(state["findings"]) == SUPPORT_AGENT_FINDINGS, "a silent run would prove little"
    assert no_network.attempts == []


def reimport_the_workflow() -> None:
    """Re-run the module's import-time tracing opt-out, whatever the environment now says."""
    spec = importlib.util.spec_from_file_location("workflow_reimported", WORKFLOW_SOURCE)
    spec.loader.exec_module(importlib.util.module_from_spec(spec))


def test_importing_the_workflow_leaves_langsmith_tracing_off() -> None:
    """The opt-out is taken by importing the module, not by anything a caller must remember."""
    reimport_the_workflow()
    assert [os.environ[name] for name in TRACING_VARIABLES] == ["false", "false"]


def test_the_tracing_opt_out_overrules_an_environment_that_asked_for_tracing(monkeypatch) -> None:
    """Offline is the tool's guarantee, so an inherited `true` must not switch tracing back on.

    A machine that develops LangChain apps commonly exports these already. If
    one of them survives into an audit, langsmith uploads each node's input and
    output -- the audited repository's paths and code identifiers -- to
    api.smith.langchain.com, which is exactly the breach this file exists to
    prevent.
    """
    for name in TRACING_VARIABLES:
        monkeypatch.setenv(name, "true")
    reimport_the_workflow()
    assert [os.environ[name] for name in TRACING_VARIABLES] == ["false", "false"]
