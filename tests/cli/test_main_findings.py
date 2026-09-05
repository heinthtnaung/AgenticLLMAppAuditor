"""The CLI writes findings.json, with or without a bill of materials.

Syft is stubbed throughout, so this runs offline. The case that matters here is
the one without dependencies: the supply-chain check has no mapping to read, so
it is left out of `checks_run` rather than named and silent -- and the file is
still written, because a check that could not look is no reason to report
nothing about the checks that could.
"""

from pathlib import Path

from artifacts.finding import SCHEMA_VERSION
from artifacts.findings_document import ADVISORY_NOT_INGESTED, MODEL_DISABLED
from artifacts.mapping import UNRESOLVED
from checks.output_handling import CHECK_NAME as QUERY_CHECK
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK
from cli_helpers import EMPTY_SCAN, read_artifact, run_cli, stub_syft
from dependency_fixtures import string_values
from deps.requirements_parser import MANIFEST_NAME as PYPI_MANIFEST
from outputs import FINDINGS_NAME, MAPPING_NAME, SURFACES_NAME

APP_NAME = "shell-tool-app"

# One privileged tool surface, so the app has something for a check to find,
# beside two data sources that map to different outcomes: `cursor.execute` is a
# call on an object whose package cannot be told (`unresolved`), and `open` is
# the language's own (`stdlib`). The mapping therefore counts more unmapped
# surfaces than unresolved ones, so a coverage block copying the wrong number
# cannot pass the test below by coincidence.
#
# That query is written out in full, so the query check reads it and clears it:
# it is named in `checks_run` and reports nothing, which is why the only finding
# below is the privileged tool.
APP_SOURCE = """from langchain_community.tools import ShellTool

tool = ShellTool()


def load_notes(cursor):
    return cursor.execute("SELECT 1"), open("notes.txt").read()
"""


def write_app(tmp_path: Path, with_manifest: bool) -> Path:
    """Write a tiny app holding one privileged tool, optionally declaring a dependency."""
    repo = tmp_path / APP_NAME
    repo.mkdir()
    (repo / "agent.py").write_text(APP_SOURCE, encoding="utf-8")
    if with_manifest:
        (repo / PYPI_MANIFEST).write_text("langchain-community==0.3.0\n", encoding="utf-8")
    return repo


def audit(monkeypatch, tmp_path: Path, with_manifest: bool = True) -> dict:
    """Run the CLI over that app and return the findings artifact it wrote."""
    stub_syft(monkeypatch, EMPTY_SCAN)
    assert run_cli(monkeypatch, write_app(tmp_path, with_manifest), tmp_path / "artifacts") == 0
    return read_artifact(tmp_path / "artifacts", APP_NAME, FINDINGS_NAME)


def audit_findings_and_mapping(monkeypatch, tmp_path) -> tuple[dict, dict]:
    """Run the CLI once and return the two artifacts that both state the unresolved count."""
    stub_syft(monkeypatch, EMPTY_SCAN)
    assert run_cli(monkeypatch, write_app(tmp_path, with_manifest=True),
                   tmp_path / "artifacts") == 0
    return (read_artifact(tmp_path / "artifacts", APP_NAME, FINDINGS_NAME),
            read_artifact(tmp_path / "artifacts", APP_NAME, MAPPING_NAME))


def test_the_findings_artifact_is_written_and_versioned(monkeypatch, tmp_path) -> None:
    """It carries its own schema version, independent of every other artifact."""
    assert audit(monkeypatch, tmp_path)["schema_version"] == SCHEMA_VERSION


def test_the_privileged_tool_reaches_the_artifact(monkeypatch, tmp_path) -> None:
    """The check runs inside the real CLI path, not only in its own test."""
    findings = audit(monkeypatch, tmp_path)["findings"]
    assert [(f["owasp_id"], f["surface_name"]) for f in findings] == [("LLM06", "ShellTool")]


def test_a_run_without_a_manifest_still_writes_findings(monkeypatch, tmp_path) -> None:
    """No dependency manifest means no mapping, which is not a reason to write nothing."""
    document = audit(monkeypatch, tmp_path, with_manifest=False)
    assert [f["rule_id"] for f in document["findings"]] == [PERMISSION_CHECK]
    assert document["coverage"]["advisory_data"] == ADVISORY_NOT_INGESTED


def test_a_run_without_a_manifest_omits_the_check_that_needed_the_mapping(
        monkeypatch, tmp_path) -> None:
    """That check had nothing to read here, and coverage must not imply it cleared the app."""
    checks_run = audit(monkeypatch, tmp_path, with_manifest=False)["coverage"]["checks_run"]
    assert SUPPLY_CHAIN_CHECK not in checks_run
    assert checks_run == sorted([PERMISSION_CHECK, QUERY_CHECK, TAINT_CHECK])


def test_a_run_with_a_manifest_names_every_static_check(monkeypatch, tmp_path) -> None:
    """Python source, a mapping to read and a tool surface: four static checks are named.

    Not `sorted(CHECK_NAMES)`: the advisory check needs Trivy and a database,
    which `stub_syft` switches off so no test depends on this machine having
    either. Its presence with advisory data is asserted in its own test.

    The query check is here because this app has both halves it needs -- Python
    to read and a tool the model can call -- and it clears the constant query.
    """
    checks_run = audit(monkeypatch, tmp_path)["coverage"]["checks_run"]
    assert checks_run == sorted(
        [PERMISSION_CHECK, QUERY_CHECK, SUPPLY_CHAIN_CHECK, TAINT_CHECK])


def test_the_coverage_agrees_with_the_surfaces_artifact(monkeypatch, tmp_path) -> None:
    """The two files must not disagree about how much of the app was looked at."""
    stub_syft(monkeypatch, EMPTY_SCAN)
    run_cli(monkeypatch, write_app(tmp_path, with_manifest=True), tmp_path / "artifacts")
    findings = read_artifact(tmp_path / "artifacts", APP_NAME, FINDINGS_NAME)
    surfaces = read_artifact(tmp_path / "artifacts", APP_NAME, SURFACES_NAME)
    assert findings["coverage"]["surfaces_considered"] == surfaces["surface_count"]


def test_the_coverage_agrees_with_the_mapping_artifact(monkeypatch, tmp_path) -> None:
    """The untraceable-surface count is a copy, and the copy must still match its source."""
    findings, mapping = audit_findings_and_mapping(monkeypatch, tmp_path)
    assert findings["coverage"]["unresolved_component_count"] == \
        mapping["reason_counts"][UNRESOLVED]


def test_the_coverage_copies_the_unresolved_reason_and_not_the_unmapped_count(
        monkeypatch, tmp_path) -> None:
    """`unmapped_count` also counts stdlib answers, so copying it would overstate the gap."""
    findings, mapping = audit_findings_and_mapping(monkeypatch, tmp_path)
    assert findings["coverage"]["unresolved_component_count"] == 1
    assert mapping["unmapped_count"] == 2


def test_the_run_records_that_no_model_was_used(monkeypatch, tmp_path) -> None:
    """Phase 3's checks are static, and the artifact says so rather than leaving nulls."""
    assert audit(monkeypatch, tmp_path)["model_run"]["status"] == MODEL_DISABLED


def test_the_written_findings_name_no_absolute_path(monkeypatch, tmp_path) -> None:
    """The artifact describes the audited app, never the machine that audited it."""
    document = audit(monkeypatch, tmp_path)
    assert [value for value in string_values(document) if value.startswith("/")] == []
