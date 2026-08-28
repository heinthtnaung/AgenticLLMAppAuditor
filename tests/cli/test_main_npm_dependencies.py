"""Auditing a JavaScript app end to end, with the generator stubbed.

Covers the CLI path for an npm repository: it reads package.json, builds an npm
bill, and joins a TypeScript surface to a declared package. Syft is replaced
throughout, so this runs on a machine that has never installed it.

Its two neighbours cover the rest of the same journey: which repositories are
readable at all is in test_main_ecosystem_choice.py, and the real generator run
over the corpus app is in test_main_npm_corpus.py.
"""

from pathlib import Path

from cli_helpers import read_artifact, run_cli, stub_syft
from dependency_fixtures import NPM_MANIFEST, PYPI_MANIFEST, TINY_PACKAGE_JSON
from deps.package_names import NPM
from main import MAPPING_NAME, SBOM_NAME

APP_NAME = "tiny-js-app"

# One agent surface importing a declared npm package, so the mapping can join.
APP_SOURCE = """import { ChatOpenAI } from "@langchain/openai";

const model = new ChatOpenAI({ model: "gpt-4o" });
"""

STUB_GENERATOR_OUTPUT = {
    "components": [{"type": "library", "name": "@langchain/openai", "version": "0.3.2"}],
}


def write_js_app(tmp_path: Path) -> Path:
    """Write a tiny npm app with one third-party surface and one declared package."""
    repo = tmp_path / APP_NAME
    repo.mkdir()
    (repo / "agent.ts").write_text(APP_SOURCE, encoding="utf-8")
    (repo / NPM_MANIFEST).write_text(TINY_PACKAGE_JSON, encoding="utf-8")
    return repo


def written(tmp_path: Path, name: str) -> dict:
    """Read one artifact this file's run left for the tiny app."""
    return read_artifact(tmp_path / "artifacts", APP_NAME, name)


def test_an_npm_app_gets_a_bill_in_the_npm_ecosystem(tmp_path, monkeypatch) -> None:
    """End to end: the CLI reads package.json and builds an npm document."""
    stub_syft(monkeypatch, STUB_GENERATOR_OUTPUT)
    assert run_cli(monkeypatch, write_js_app(tmp_path), tmp_path / "artifacts") == 0
    components = written(tmp_path, SBOM_NAME)["components"]
    assert [(c["name"], c["ecosystem"]) for c in components] == [("@langchain/openai", NPM)]


def test_the_npm_bill_records_the_manifest_it_read(tmp_path, monkeypatch) -> None:
    """`scanned_manifests` and `declared_in` both name package.json, not requirements.txt."""
    stub_syft(monkeypatch, STUB_GENERATOR_OUTPUT)
    run_cli(monkeypatch, write_js_app(tmp_path), tmp_path / "artifacts")
    document = written(tmp_path, SBOM_NAME)
    assert document["scanned_manifests"] == [NPM_MANIFEST]
    assert document["components"][0]["declared_in"] == NPM_MANIFEST


def test_the_npm_app_maps_its_surface_to_the_declared_package(tmp_path, monkeypatch) -> None:
    """The join works across the whole CLI path, not just in the mapping unit."""
    stub_syft(monkeypatch, STUB_GENERATOR_OUTPUT)
    run_cli(monkeypatch, write_js_app(tmp_path), tmp_path / "artifacts")
    document = written(tmp_path, MAPPING_NAME)
    assert document["mapped_count"] == 1
    assert document["entries"][0]["component_name"] == "@langchain/openai"


def test_a_mixed_repo_still_gets_its_surfaces(tmp_path, monkeypatch, capsys) -> None:
    """A refused bill is not a failed run: the static artifacts are written anyway."""
    stub_syft(monkeypatch, STUB_GENERATOR_OUTPUT)
    repo = write_js_app(tmp_path)
    (repo / PYPI_MANIFEST).write_text("streamlit\n", encoding="utf-8")
    assert run_cli(monkeypatch, repo, tmp_path / "artifacts") == 0
    assert "no bill of materials" in capsys.readouterr().err
    assert not (tmp_path / "artifacts" / APP_NAME / SBOM_NAME).exists()
