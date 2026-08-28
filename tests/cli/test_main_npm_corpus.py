"""The real JS corpus app, audited with the real generator: what a lockfile buys.

Covers one thing the stubbed runs cannot: `corpus/oss-app-langgraphjs-starter`
is the only fixture shipping a lockfile, so it is the only one that can show
`locked` versions reaching an artifact. The figures below were measured on that
run. It skips when Syft is not installed or the app is not downloaded, and both
skips are visible in the summary.

The stubbed npm path is in test_main_npm_dependencies.py.
"""

from pathlib import Path

import pytest

from cli_helpers import read_artifact, run_cli
from conftest import app_path, require_corpus
from dependency_fixtures import JS_MANIFESTS, LANGGRAPHJS_STARTER
from deps import syft_runner
from artifacts.sbom import LOCKED, UNKNOWN
from main import SBOM_NAME

# Measured on the real scan: yarn.lock resolved 80 installed copies, and
# package.json declares two more it did not.
EXPECTED_COMPONENT_COUNT = 82
EXPECTED_LOCKED_COUNT = 80
EXPECTED_UNKNOWN_COUNT = 2


def corpus_js_sbom(tmp_path: Path, monkeypatch) -> dict:
    """Audit the real JS corpus app with the real generator and read its sbom.json."""
    if not syft_runner.is_available():
        pytest.skip("syft is not installed - see the README prerequisites")
    require_corpus(LANGGRAPHJS_STARTER)
    assert run_cli(monkeypatch, app_path(LANGGRAPHJS_STARTER), tmp_path / "artifacts") == 0
    return read_artifact(tmp_path / "artifacts", LANGGRAPHJS_STARTER, SBOM_NAME)


def test_the_corpus_js_app_reads_its_manifest_and_its_lockfile(tmp_path, monkeypatch) -> None:
    """The real run records both files, which is what earns the `locked` versions."""
    assert corpus_js_sbom(tmp_path, monkeypatch)["scanned_manifests"] == JS_MANIFESTS


def test_the_corpus_js_app_bills_every_installed_copy(tmp_path, monkeypatch) -> None:
    """82 records: 80 copies yarn.lock resolved, plus two declared packages it did not."""
    sources = [c["version_source"] for c in corpus_js_sbom(tmp_path, monkeypatch)["components"]]
    assert len(sources) == EXPECTED_COMPONENT_COUNT
    assert sources.count(LOCKED) == EXPECTED_LOCKED_COUNT
    assert sources.count(UNKNOWN) == EXPECTED_UNKNOWN_COUNT
