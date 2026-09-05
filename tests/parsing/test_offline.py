"""Doing the audit opens no socket: the project's central safety boundary, exercised.

Audited source is often proprietary, so the guarantee that it never leaves the
machine is the reason the tool can be pointed at a private repository at all.
Every test here performs a real operation on the audit path -- extract,
serialise, build the AIBOM and the mapping, compile and run the audit graph --
with the socket type replaced by one that refuses and records. The count of
recorded attempts is the assertion.

That proves the paths these tests walk, and only those. **The gap is closed by
`test_offline_containment.py`**, which reads the source and the settings
instead: which modules may open a connection at all, which may import
chromadb, and the third-party defaults -- Syft's update check, Chroma's
telemetry, LangSmith's tracing -- that would reach out from a process this
file's blocked socket cannot watch.

The audit path only. The knowledge store is held to the same guarantee in
`tests/retrieval/test_store_offline.py`, which was split out of this file and
shares its refusing socket through `tests/offline_fixtures.py`; what the store
*does*, as opposed to what it must never do, is `tests/retrieval/test_store.py`.

**The audited tree is written by the test**, by `mixed_app_fixtures`, since the
pinned corpus was removed -- so its inputs were chosen by the same author as
the code. What that gives up is worth naming: no oversized file, no non-UTF-8
source, no malformed `.ts`, no unforeseen code shape, so a socket opened only
on one of those would not be seen here. The tree is deliberately
mixed-language, carries an untrusted value reaching the agent, builds one
query by interpolation and constructs its agent with no callback argument, so
all five planned checks have a subject and each one reports; and every count
below is a literal: a silent run would prove little, and an empty one nothing.
"""

import json

from checks import workflow
from checks.auditability import CHECK_NAME as AUDITABILITY_CHECK
from checks.output_handling import CHECK_NAME as QUERY_CHECK
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK
from parsing.languages import PYTHON, TYPESCRIPT
from artifacts.aibom import build_aibom
from conftest import scan_to_json
from parsing.extractor import extract_repo
from parsing.repo_loader import local_module_names
from artifacts.mapping import THIRD_PARTY, build_mapping
from dependency_fixtures import pypi_sbom
from mixed_app_fixtures import (
    MIXED_APP_AI_COMPONENTS,
    MIXED_APP_FINDINGS,
    MIXED_APP_JOINS,
    MIXED_APP_SURFACES,
    PYTHON_FILE,
    UNSAFE_QUERY_LINE,
    UNTRUSTED_INPUT_LINE,
    write_mixed_app,
)
from offline_fixtures import no_network  # noqa: F401  (used as a fixture)

# Every check the workflow can plan for this app: the widest path through it.
# The advisory check is the one absent, and deliberately: it needs Trivy's
# database, which no test on a clean checkout has.
WHOLE_APP_PLAN = [PERMISSION_CHECK, SUPPLY_CHAIN_CHECK, TAINT_CHECK, QUERY_CHECK,
                  AUDITABILITY_CHECK]


def test_extracting_a_repository_touches_no_network(tmp_path, no_network) -> None:
    """A full extraction over both backends completes with sockets blocked, and attempts none."""
    surfaces = extract_repo(str(write_mixed_app(tmp_path))).surfaces
    assert len(surfaces) == MIXED_APP_SURFACES, "extraction produced too little to prove much"
    assert no_network.attempts == []


def test_extraction_reaches_both_language_backends(tmp_path, no_network) -> None:
    """Guard: one silent backend would leave half the parsing untested here."""
    surfaces = extract_repo(str(write_mixed_app(tmp_path))).surfaces
    assert {surface.language for surface in surfaces} == {PYTHON, TYPESCRIPT}
    assert no_network.attempts == []


def test_serialising_the_artifact_touches_no_network(tmp_path, no_network) -> None:
    """Writing the artifact is local too: nothing is reported to anywhere."""
    document = json.loads(scan_to_json(str(write_mixed_app(tmp_path))))
    assert len(document["surfaces"]) == MIXED_APP_SURFACES
    assert no_network.attempts == []


def test_building_the_aibom_touches_no_network(tmp_path, no_network) -> None:
    """The AIBOM is derived from surfaces already in memory: nothing is looked up."""
    surfaces = extract_repo(str(write_mixed_app(tmp_path))).surfaces
    assert build_aibom(surfaces)["component_count"] == MIXED_APP_AI_COMPONENTS
    assert no_network.attempts == []


def test_building_the_mapping_touches_no_network(tmp_path, no_network) -> None:
    """The import-to-package join is decided from local tables, never a package index."""
    repo = write_mixed_app(tmp_path)
    surfaces = extract_repo(str(repo)).surfaces
    mapping = build_mapping(surfaces, pypi_sbom(), local_module_names(str(repo)))
    assert mapping["surface_count"] == MIXED_APP_SURFACES
    assert no_network.attempts == []


def test_the_mapping_that_opened_no_socket_still_joined_something(tmp_path, no_network) -> None:
    """Guard: a mapping that resolved nothing would need no index to consult."""
    repo = write_mixed_app(tmp_path)
    mapping = build_mapping(extract_repo(str(repo)).surfaces, pypi_sbom(),
                            local_module_names(str(repo)))
    joined = [entry for entry in mapping["entries"] if entry["reason"] == THIRD_PARTY]
    assert len(joined) == MIXED_APP_JOINS
    assert no_network.attempts == []


def test_compiling_the_audit_graph_touches_no_network(no_network) -> None:
    """Building the loop is local: the framework looks nothing up as it wires it."""
    assert workflow.build_graph() is not None
    assert no_network.attempts == []


def audit_the_mixed_app(tmp_path) -> dict:
    """Extract, map and run every planned check over the written tree."""
    repo = write_mixed_app(tmp_path)
    surfaces = extract_repo(str(repo)).surfaces
    mapping = build_mapping(surfaces, pypi_sbom(), local_module_names(str(repo)))
    return workflow.audit(str(repo), surfaces, mapping, WHOLE_APP_PLAN)


def test_running_the_whole_audit_workflow_touches_no_network(tmp_path, no_network) -> None:
    """Every check the planner can run, over a whole app, with every socket refused."""
    state = audit_the_mixed_app(tmp_path)
    assert len(state["findings"]) == MIXED_APP_FINDINGS, "a silent run would prove little"
    assert no_network.attempts == []


def test_every_planned_check_really_ran_with_no_socket(tmp_path, no_network) -> None:
    """Guard: the widest path is only wide if each check was reached, not merely listed."""
    assert audit_the_mixed_app(tmp_path)["checks_run"] == WHOLE_APP_PLAN
    assert no_network.attempts == []


def test_each_planned_check_reported_its_own_finding_with_no_socket(
        tmp_path, no_network) -> None:
    """Reached is not did something: five findings from one check would pass a count."""
    rule_ids = [finding.rule_id for finding in audit_the_mixed_app(tmp_path)["findings"]]
    assert sorted(rule_ids) == sorted(WHOLE_APP_PLAN)
    assert no_network.attempts == []


def test_the_query_check_reported_its_own_line_with_no_socket(tmp_path, no_network) -> None:
    """The newest check, held to the same guarantee: it reads source and opens nothing."""
    queries = [finding for finding in audit_the_mixed_app(tmp_path)["findings"]
               if finding.rule_id == QUERY_CHECK]
    assert [(f.file, f.line) for f in queries] == [(PYTHON_FILE, UNSAFE_QUERY_LINE)]
    assert no_network.attempts == []


def test_the_taint_trace_followed_a_real_flow_with_no_socket(tmp_path, no_network) -> None:
    """The check whose logic runs nowhere else under a blocked socket, anchored on its source."""
    traced = [finding for finding in audit_the_mixed_app(tmp_path)["findings"]
              if finding.rule_id == TAINT_CHECK]
    assert [(f.file, f.line) for f in traced] == [(PYTHON_FILE, UNTRUSTED_INPUT_LINE)]
    assert no_network.attempts == []

