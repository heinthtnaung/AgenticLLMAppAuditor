"""The CLI's advisory path: Trivy's report joins the mapping, or degrades to null.

Syft and Trivy are both stubbed, so this runs offline with neither installed
and no subprocess ever starts. `stub_syft` switches Trivy OFF -- that is the
degradation case -- and `stub_trivy` switches it back ON with a hand-built
report whose purl is exactly the component the stubbed scan makes the mapping
join, so the advisory reaches a real surface through the real CLI path.
"""

from pathlib import Path

from advisory_fixtures import (
    ADVISORY_ID,
    ADVISORY_PURL,
    DB_UPDATED_AT,
    TRIVY_VERSION,
    stub_trivy,
)
from artifacts.findings_document import ADVISORY_NOT_INGESTED, ADVISORY_SNAPSHOT
from checks.known_advisory import CHECK_NAME as ADVISORY_CHECK
from checks.run_checks import EDGE_CHECKS, GRAPH_CHECKS
from cli_helpers import read_artifact, run_cli, stub_syft
from deps import trivy_runner
from deps.requirements_parser import MANIFEST_NAME as PYPI_MANIFEST
from outputs import FINDINGS_NAME, REPORT_NAME

APP_NAME = "advisory-app"

# One agent surface importing langchain, so the mapping joins it to the stubbed
# component below and the hand-built advisory has a surface to anchor on.
APP_SOURCE = """from langchain.agents import AgentExecutor

agent = AgentExecutor.from_agent_and_tools(agent=None, tools=[])
"""
AGENT_SURFACE_ID = "main.py:3:AGENT_DEF:AgentExecutor.from_agent_and_tools"

# The component the mapping resolves the surface to: its purl is ADVISORY_PURL.
STUB_GENERATOR_OUTPUT = {
    "components": [{"type": "library", "name": "langchain", "version": "0.3.25"}],
}

PIN_FIELDS = ("advisory_generator_name", "advisory_generator_version",
              "advisory_db_updated_at")


def write_app(tmp_path: Path) -> Path:
    """Write a tiny LLM app with one joinable surface and one declared package."""
    repo = tmp_path / APP_NAME
    repo.mkdir()
    (repo / "main.py").write_text(APP_SOURCE, encoding="utf-8")
    (repo / PYPI_MANIFEST).write_text("langchain==0.3.25\n", encoding="utf-8")
    return repo


def audit(monkeypatch, tmp_path: Path, with_trivy: bool = True,
          out: str = "artifacts") -> dict:
    """Run the CLI over that app and return the findings artifact it wrote."""
    stub_syft(monkeypatch, STUB_GENERATOR_OUTPUT)
    if with_trivy:
        stub_trivy(monkeypatch)
    assert run_cli(monkeypatch, tmp_path / APP_NAME, tmp_path / out) == 0
    return read_artifact(tmp_path / out, APP_NAME, FINDINGS_NAME)


def test_the_advisory_finding_reaches_the_artifact_anchored_on_its_surface(
        monkeypatch, tmp_path) -> None:
    """The whole join runs inside the real CLI path: scan, index, mapping, finding."""
    write_app(tmp_path)
    findings = audit(monkeypatch, tmp_path)["findings"]
    advisory = [f for f in findings if f["rule_id"] == ADVISORY_CHECK]
    assert [(f["advisory_id"], f["purl"]) for f in advisory] == [(ADVISORY_ID, ADVISORY_PURL)]
    assert (advisory[0]["file"], advisory[0]["line"]) == ("main.py", 3)
    assert advisory[0]["surface_id"] == AGENT_SURFACE_ID


def test_with_advisory_data_every_known_check_ran(monkeypatch, tmp_path) -> None:
    """The one setup where checks_run is finally every check the graph can run.

    Every check *except* the edge ones, which is what `GRAPH_CHECKS` names.
    `run_cli` passes no `--semantic-probe` here, so the probe was offered no
    model, produced nothing, and is absent -- which is this project's absence
    rule, not an omission: naming it would claim a model read this app's prompt
    templates when none was consulted. `tests/cli/test_main_probe.py` runs the
    flag, so do not restore `sorted(CHECK_NAMES)` to cover the probe.
    """
    write_app(tmp_path)
    coverage = audit(monkeypatch, tmp_path)["coverage"]
    assert coverage["checks_run"] == sorted(GRAPH_CHECKS)


def test_a_default_audit_consults_no_model_for_the_edge_check(monkeypatch, tmp_path) -> None:
    """Guard: the subtraction above would pass on an edge check that ran unasked."""
    write_app(tmp_path)
    document = audit(monkeypatch, tmp_path)
    assert EDGE_CHECKS
    assert set(document["coverage"]["checks_run"]) & set(EDGE_CHECKS) == set()
    assert [p for p in document["probes"] if p["probe_name"] in EDGE_CHECKS] == []


def test_the_coverage_carries_the_snapshot_and_its_pin(monkeypatch, tmp_path) -> None:
    """Generator, version and the database's own date: what makes the scan a dated claim."""
    write_app(tmp_path)
    coverage = audit(monkeypatch, tmp_path)["coverage"]
    assert coverage["advisory_data"] == ADVISORY_SNAPSHOT
    assert coverage["advisory_generator_name"] == trivy_runner.GENERATOR_NAME
    assert coverage["advisory_generator_version"] == TRIVY_VERSION
    assert coverage["advisory_db_updated_at"] == DB_UPDATED_AT
    assert coverage["advisory_unreached_component_count"] == 0


def test_the_written_report_renders_the_advisory_evidence(monkeypatch, tmp_path) -> None:
    """The pin, the advisory and the quoted vector all reach the file a person reads."""
    write_app(tmp_path)
    audit(monkeypatch, tmp_path)
    text = (tmp_path / "artifacts" / APP_NAME / REPORT_NAME).read_text(encoding="utf-8")
    assert f"Known-vulnerability data: `{trivy_runner.GENERATOR_NAME}` {TRIVY_VERSION}" in text
    assert f"- **Advisory**: `{ADVISORY_ID}`" in text
    assert ", quoted)**: `CVSS:3.1/" in text


def test_two_runs_write_byte_identical_findings(monkeypatch, tmp_path) -> None:
    """The advisory join adds nothing clock- or order-shaped to the determinism rule."""
    write_app(tmp_path)
    audit(monkeypatch, tmp_path, out="first")
    audit(monkeypatch, tmp_path, out="second")
    first = (tmp_path / "first" / APP_NAME / FINDINGS_NAME).read_bytes()
    assert first == (tmp_path / "second" / APP_NAME / FINDINGS_NAME).read_bytes()


def test_without_trivy_the_run_degrades_to_no_advisory_data(monkeypatch, tmp_path) -> None:
    """No tool means not_ingested, a null pin, and the check absent -- never null-pinned claims."""
    write_app(tmp_path)
    document = audit(monkeypatch, tmp_path, with_trivy=False)
    coverage = document["coverage"]
    assert coverage["advisory_data"] == ADVISORY_NOT_INGESTED
    assert all(coverage[field] is None for field in PIN_FIELDS)
    assert coverage["advisory_unreached_component_count"] is None
    assert ADVISORY_CHECK not in coverage["checks_run"]


def test_a_missing_database_degrades_the_same_way_without_scanning(
        monkeypatch, tmp_path) -> None:
    """Trivy installed but no cached database: no scan runs, and nothing is claimed."""
    write_app(tmp_path)
    def refuse_to_scan(*_args, **_kwargs) -> dict:
        """Fail the test if the CLI scans despite having no database date."""
        raise AssertionError("a scan ran with no database behind it")

    stub_syft(monkeypatch, STUB_GENERATOR_OUTPUT)
    monkeypatch.setattr(trivy_runner, "is_available", lambda: True)
    monkeypatch.setattr(trivy_runner, "db_snapshot_date", lambda cache_dir=None: None)
    monkeypatch.setattr(trivy_runner, "scan", refuse_to_scan)
    assert run_cli(monkeypatch, tmp_path / APP_NAME, tmp_path / "artifacts") == 0
    coverage = read_artifact(tmp_path / "artifacts", APP_NAME, FINDINGS_NAME)["coverage"]
    assert coverage["advisory_data"] == ADVISORY_NOT_INGESTED
    assert ADVISORY_CHECK not in coverage["checks_run"]
