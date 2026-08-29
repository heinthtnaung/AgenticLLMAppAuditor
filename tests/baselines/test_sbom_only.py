"""Baseline B reports components, one per name, with nothing to anchor them to.

Two decisions carry the module and both are asserted here. It calls Syft rather
than reading the auditor's `sbom.json`, which holds this project's own
`declared` and `version_source` judgements. And it reports one finding per
component *name*, never per (name, version): `Finding.id` anchors on
`component_name` before `purl`, so a package Syft saw at two versions would
produce two identical ids and `build_findings_document` would refuse the
document outright.
"""

from pathlib import Path

import pytest

from artifacts.finding import STATIC, Finding
from artifacts.findings_document import (
    MODEL_DISABLED,
    build_findings_document,
    coverage,
    model_run,
)
from baseline_fixtures import EMPTY_SYFT_DOCUMENT, NAMELESS_SYFT_DOCUMENT, stub_syft
from baselines.sbom_only import CHECK_NAME, OWASP_ID, component_names, scan_repo
from dependency_fixtures import (
    CORPUS_GENERATOR_OUTPUT,
    JS_GENERATOR_SAMPLE,
    TINY_PACKAGE_JSON,
)
from deps import syft_runner
from deps.npm_manifest import MANIFEST_NAME as NPM_MANIFEST

# The recorded npm scan lists eight components and five distinct names:
# `langsmith` at three versions and `@langchain/openai` at two.
JS_COMPONENT_COUNT = 8
JS_DISTINCT_NAMES = [
    "@langchain/community", "@langchain/langgraph", "@langchain/openai", "langsmith", "zod",
]

# The recorded Python scan, whose fourth component is the manifest file itself.
PYTHON_LIBRARY_NAMES = ["langchain", "langchain-litellm", "openai"]

SYFT_FAILURE = "syft scan failed: no such directory"


def scan_with(monkeypatch: pytest.MonkeyPatch, document: dict, root: Path) -> list[Finding]:
    """Run Baseline B over a directory with Syft answered from a recorded document."""
    stub_syft(monkeypatch, document)
    return scan_repo(str(root))


def test_one_package_reported_at_two_versions_yields_one_finding(
        monkeypatch, tmp_path: Path) -> None:
    """The duplicate-id trap: eight components, five names, five findings."""
    (tmp_path / NPM_MANIFEST).write_text(TINY_PACKAGE_JSON, encoding="utf-8")
    findings = scan_with(monkeypatch, JS_GENERATOR_SAMPLE, tmp_path)
    assert len(JS_GENERATOR_SAMPLE["components"]) == JS_COMPONENT_COUNT
    assert [f.component_name for f in findings] == JS_DISTINCT_NAMES


def test_the_findings_document_accepts_that_scan(monkeypatch, tmp_path: Path) -> None:
    """The trap is only avoided if the document really builds; ids are checked there."""
    (tmp_path / NPM_MANIFEST).write_text(TINY_PACKAGE_JSON, encoding="utf-8")
    findings = scan_with(monkeypatch, JS_GENERATOR_SAMPLE, tmp_path)
    document = build_findings_document(
        findings, [], coverage(0, [CHECK_NAME], risk_classes_checked=[OWASP_ID]),
        model_run(MODEL_DISABLED))
    assert document["finding_count"] == len(JS_DISTINCT_NAMES)


def test_one_finding_per_version_would_have_been_refused_as_a_duplicate() -> None:
    """Mutation check: the version-keyed alternative collides, exactly as predicted."""
    versions = ["0.1.48", "0.1.61"]
    findings = [
        Finding(owasp_id=OWASP_ID, rule_id=CHECK_NAME, title="unreviewed", detection=STATIC,
                component_name="langsmith", purl=f"pkg:npm/langsmith@{version}")
        for version in versions
    ]
    assert findings[0].id == findings[1].id
    with pytest.raises(ValueError, match="share an id"):
        build_findings_document(findings, [], coverage(0, [CHECK_NAME]),
                                model_run(MODEL_DISABLED))


def test_component_names_returns_distinct_names_in_a_stable_order() -> None:
    """Sorted names, because the artifact must not depend on Syft's own ordering."""
    assert component_names(JS_GENERATOR_SAMPLE) == JS_DISTINCT_NAMES


def test_a_component_that_is_not_a_library_is_not_reported() -> None:
    """Syft lists the manifest file as a component; it is not a dependency."""
    assert component_names(CORPUS_GENERATOR_OUTPUT) == PYTHON_LIBRARY_NAMES


def test_a_component_with_no_name_is_ignored_rather_than_reported_blank() -> None:
    """A nameless component is neither a finding to report nor an error to raise."""
    assert component_names(NAMELESS_SYFT_DOCUMENT) == []


def test_a_document_with_no_components_produces_no_finding(monkeypatch, tmp_path: Path) -> None:
    """An app with no manifest is nothing to report, not an empty bill of health."""
    assert scan_with(monkeypatch, EMPTY_SYFT_DOCUMENT, tmp_path) == []


def test_every_finding_carries_no_file_and_no_line(monkeypatch, tmp_path: Path) -> None:
    """The whole ceiling result rests on this: a component sits nowhere in the code."""
    findings = scan_with(monkeypatch, CORPUS_GENERATOR_OUTPUT, tmp_path)
    assert [(f.file, f.line) for f in findings] == [(None, None)] * len(findings)


def test_every_finding_carries_no_surface_either(monkeypatch, tmp_path: Path) -> None:
    """No surface model at all, so there is nothing for `matches_key` to compare."""
    findings = scan_with(monkeypatch, CORPUS_GENERATOR_OUTPUT, tmp_path)
    assert {(f.surface_id, f.surface_kind, f.surface_name) for f in findings} == {(None,) * 3}


def test_every_finding_is_reported_under_the_supply_chain_class(
        monkeypatch, tmp_path: Path) -> None:
    """LLM03 in the 2025 numbering, and this system reports nothing else."""
    findings = scan_with(monkeypatch, CORPUS_GENERATOR_OUTPUT, tmp_path)
    assert {f.owasp_id for f in findings} == {"LLM03"}


def test_the_purl_carries_no_version(monkeypatch, tmp_path: Path) -> None:
    """This baseline makes no claim about which version is installed."""
    findings = scan_with(monkeypatch, CORPUS_GENERATOR_OUTPUT, tmp_path)
    assert [f.purl for f in findings] == [f"pkg:pypi/{name}" for name in PYTHON_LIBRARY_NAMES]


def test_an_app_declaring_package_json_gets_npm_purls(monkeypatch, tmp_path: Path) -> None:
    """The ecosystem is read from the manifest that is present, not guessed per name."""
    (tmp_path / NPM_MANIFEST).write_text(TINY_PACKAGE_JSON, encoding="utf-8")
    findings = scan_with(monkeypatch, JS_GENERATOR_SAMPLE, tmp_path)
    assert findings[-1].purl == "pkg:npm/zod"


def test_the_directory_scanned_is_the_app_itself(monkeypatch, tmp_path: Path) -> None:
    """Syft is asked about the audited app, which is what makes this a real scan."""
    asked = stub_syft(monkeypatch, EMPTY_SYFT_DOCUMENT)
    scan_repo(str(tmp_path))
    assert asked == [tmp_path]


def test_a_failing_generator_is_not_swallowed(monkeypatch, tmp_path: Path) -> None:
    """Rule 8: with no Syft output there is no bill of materials, and no empty result either."""
    def fail(_app_dir: Path) -> dict:
        raise RuntimeError(SYFT_FAILURE)

    monkeypatch.setattr(syft_runner, "scan", fail)
    with pytest.raises(RuntimeError, match=SYFT_FAILURE):
        scan_repo(str(tmp_path))
