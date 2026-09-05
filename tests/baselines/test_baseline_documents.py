"""What each baseline's `findings.json` claims to have examined, and what it refuses to.

`coverage` is the field that stops a short findings list reading as a clean
bill, and it protects a baseline exactly as it protects the auditor -- a
baseline claiming to have looked at what it never looked at is unfair in its
own favour, which would flatter this project's comparison rather than the
baseline's.

Both documents are built through `run_baseline.build_documents`, the same call
the CLI makes, so nothing here asserts a shape the tool does not produce.
"""

import json
from pathlib import Path

import pytest

from baseline_fixtures import EMPTY_SYFT_DOCUMENT, stub_syft, write_tiny_app
from baselines.sbom_only import CHECK_NAME
from artifacts.finding import SCHEMA_VERSION as FINDINGS_SCHEMA_VERSION
from artifacts.findings_document import ADVISORY_NOT_INGESTED
from artifacts.surface import SCHEMA_VERSION as SURFACES_SCHEMA_VERSION
from baselines.static_rules import CHECK_NAMES
from dependency_fixtures import PYPI_GENERATOR_OUTPUT
from run_baseline import SBOM_ONLY, STATIC_RULES, build_documents

# What Baseline A reports on the one-match-per-rule app: five surfaces, and the
# four classes its rule list covers. LLM03 is absent -- it has no rule for one.
STATIC_RULES_CLASSES = ["AUDITABILITY", "LLM01", "LLM02", "LLM06"]
STATIC_RULES_SURFACES = 5
SUPPLY_CHAIN = "LLM03"

# What Baseline B reports: the supply-chain class alone.
SBOM_ONLY_CLASSES = ["LLM03"]
OTHER_CLASSES = ["LLM01", "LLM02", "LLM06", "AUDITABILITY"]


def documents(system: str, repo_path: str) -> tuple[dict, dict]:
    """Build one baseline's two artifacts and return them parsed."""
    findings_json, surfaces_json = build_documents(system, repo_path)
    return json.loads(findings_json), json.loads(surfaces_json)


@pytest.fixture
def static_rules_documents(tmp_path: Path) -> tuple[dict, dict]:
    """Baseline A's findings and surfaces for the one-match-per-rule app."""
    return documents(STATIC_RULES, write_tiny_app(tmp_path))


@pytest.fixture
def sbom_only_documents(monkeypatch, tmp_path: Path) -> tuple[dict, dict]:
    """Baseline B's findings and surfaces, Syft answered from recorded output."""
    stub_syft(monkeypatch, PYPI_GENERATOR_OUTPUT)
    return documents(SBOM_ONLY, str(tmp_path))


@pytest.mark.parametrize("system", (STATIC_RULES, SBOM_ONLY))
def test_neither_baseline_counts_its_unresolved_components(
        system, monkeypatch, tmp_path: Path) -> None:
    """Null, never 0: neither built a mapping, so none of them resolved anything."""
    stub_syft(monkeypatch, PYPI_GENERATOR_OUTPUT)
    findings, _ = documents(system, write_tiny_app(tmp_path))
    assert findings["coverage"]["unresolved_component_count"] is None


@pytest.mark.parametrize("system", (STATIC_RULES, SBOM_ONLY))
def test_neither_baseline_ran_a_model(system, monkeypatch, tmp_path: Path) -> None:
    """A baseline is deterministic code; `disabled` says so and names no model."""
    stub_syft(monkeypatch, PYPI_GENERATOR_OUTPUT)
    findings, _ = documents(system, write_tiny_app(tmp_path))
    assert findings["model_run"]["status"] == "disabled"
    assert findings["model_run"]["model_identifier"] is None


@pytest.mark.parametrize("system", (STATIC_RULES, SBOM_ONLY))
def test_neither_baseline_emits_a_probe(system, monkeypatch, tmp_path: Path) -> None:
    """`_surface_anchor` parses a probe's id, so a baseline probe would crash the scorer."""
    stub_syft(monkeypatch, PYPI_GENERATOR_OUTPUT)
    findings, _ = documents(system, write_tiny_app(tmp_path))
    assert (findings["probes"], findings["probe_count"]) == ([], 0)


def test_baseline_a_names_every_rule_it_ran(static_rules_documents) -> None:
    """The rules ran whether or not they matched, so all five are `checks_run`."""
    findings, _ = static_rules_documents
    assert findings["coverage"]["checks_run"] == sorted(CHECK_NAMES)


def test_baseline_a_checks_four_risk_classes_and_not_the_supply_chain(
        static_rules_documents) -> None:
    """It has no rule for LLM03, so that class is absent rather than present and empty."""
    findings, _ = static_rules_documents
    assert findings["coverage"]["risk_classes_checked"] == STATIC_RULES_CLASSES
    assert SUPPLY_CHAIN not in findings["coverage"]["risk_classes_checked"]


def test_baseline_a_counts_the_surfaces_it_derived(static_rules_documents) -> None:
    """`surfaces_considered` and the surfaces file agree, or the two contradict each other."""
    findings, surfaces = static_rules_documents
    assert findings["coverage"]["surfaces_considered"] == STATIC_RULES_SURFACES
    assert surfaces["surface_count"] == STATIC_RULES_SURFACES


def test_baseline_a_writes_the_surfaces_its_findings_named(static_rules_documents) -> None:
    """Derived, not empty: every finding's surface id appears in the surfaces file."""
    findings, surfaces = static_rules_documents
    assert ({s["id"] for s in surfaces["surfaces"]}
            == {f["surface_id"] for f in findings["findings"]})


def test_baseline_b_checks_the_supply_chain_class_alone(sbom_only_documents) -> None:
    """Everything else is absent, so silence is never read as a clean result."""
    findings, _ = sbom_only_documents
    assert findings["coverage"]["risk_classes_checked"] == SBOM_ONLY_CLASSES
    assert [c for c in OTHER_CLASSES if c in findings["coverage"]["risk_classes_checked"]] == []


def test_baseline_b_names_its_one_check(sbom_only_documents) -> None:
    """One check ran: the component scan, and nothing else pretends to have."""
    findings, _ = sbom_only_documents
    assert findings["coverage"]["checks_run"] == [CHECK_NAME]


def test_baseline_b_writes_a_legitimately_empty_surfaces_file(sbom_only_documents) -> None:
    """It has no surface model at all, so an empty list is the honest answer here."""
    _, surfaces = sbom_only_documents
    assert (surfaces["surfaces"], surfaces["surface_count"]) == ([], 0)
    assert surfaces["skipped_files"] == []


def test_baseline_b_claims_no_check_when_syft_reports_nothing(monkeypatch, tmp_path) -> None:
    """No manifest means nothing was examined, as when the auditor has no mapping to read."""
    stub_syft(monkeypatch, EMPTY_SYFT_DOCUMENT)
    findings, _ = documents(SBOM_ONLY, str(tmp_path))
    assert findings["coverage"]["checks_run"] == []
    assert findings["coverage"]["risk_classes_checked"] == []


@pytest.mark.parametrize("system", (STATIC_RULES, SBOM_ONLY))
def test_both_baselines_report_advisory_data_as_not_ingested(
        system, monkeypatch, tmp_path: Path) -> None:
    """Neither reads advisories, so neither may imply a component was checked against one."""
    stub_syft(monkeypatch, PYPI_GENERATOR_OUTPUT)
    findings, _ = documents(system, write_tiny_app(tmp_path))
    assert findings["coverage"]["advisory_data"] == ADVISORY_NOT_INGESTED


@pytest.mark.parametrize("system", (STATIC_RULES, SBOM_ONLY))
def test_neither_baseline_narrows_a_check(system, monkeypatch, tmp_path: Path) -> None:
    """A baseline has no planner, so it says `[]` rather than inventing a record.

    `build_findings_document` defaults `checks_narrowed` to `[]`, which is what
    lets `run_baseline.py` stay unedited through task 7.4 -- a producer with no
    model must not have to fabricate a narrowing to satisfy the schema. The
    field is still present, because a comparison that measured two artifact
    shapes would not be measuring two systems.
    """
    stub_syft(monkeypatch, PYPI_GENERATOR_OUTPUT)
    findings, _ = documents(system, write_tiny_app(tmp_path))
    assert findings["checks_narrowed"] == []


# What the scorer reads off every produced finding, whichever system wrote it.
SCORED_FINDING_FIELDS = {"finding_id", "owasp_id", "file", "line",
                         "surface_kind", "surface_name"}


@pytest.mark.parametrize("system", (STATIC_RULES, SBOM_ONLY))
def test_both_baselines_write_the_schema_versions_the_auditor_writes(
        system, monkeypatch, tmp_path: Path) -> None:
    """The comparison measures two systems, so it must not measure two artifact shapes."""
    stub_syft(monkeypatch, PYPI_GENERATOR_OUTPUT)
    findings, surfaces = documents(system, write_tiny_app(tmp_path))
    assert findings["schema_version"] == FINDINGS_SCHEMA_VERSION
    assert surfaces["schema_version"] == SURFACES_SCHEMA_VERSION


@pytest.mark.parametrize("system", (STATIC_RULES, SBOM_ONLY))
def test_every_produced_finding_carries_the_fields_the_join_reads(
        system, monkeypatch, tmp_path: Path) -> None:
    """`matches_key` reads these six off each finding; a missing one is a crash mid-score."""
    stub_syft(monkeypatch, PYPI_GENERATOR_OUTPUT)
    findings, _ = documents(system, write_tiny_app(tmp_path))
    assert findings["findings"]
    for finding in findings["findings"]:
        assert SCORED_FINDING_FIELDS <= set(finding)
