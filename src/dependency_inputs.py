"""Decides whether an app's dependencies can be read, and builds the bills.

Split out of `main.py`, which had grown past the ~200-line cap as the audit
gained a planner, a probe and a timer. This is the half that answers one
question -- what does this repository declare, and what do those declarations
make -- so `main.py` is left as the command: parse, run, write, report.
"""

from pathlib import Path

from artifacts.mapping import build_mapping, mapping_to_json
from artifacts.cyclonedx import to_cyclonedx
from artifacts.sbom import build_sbom, sbom_to_json
from artifacts.surface import Surface
from deps import npm_manifest, syft_runner
from deps.package_names import NPM, PYPI
from deps.requirements_parser import (
    MANIFEST_NAME as PYPI_MANIFEST_NAME, manifests_present, read_requirements)
from outputs import CYCLONEDX_NAME, MAPPING_NAME, SBOM_NAME
from parsing.repo_loader import local_module_names

# Naming both files, not just both ecosystems: the reader has to know which two
# manifests to look at to understand why no bill was produced.
MIXED_MANIFEST_REASON = (
    f"both a Python ({PYPI_MANIFEST_NAME}) and an npm ({npm_manifest.MANIFEST_NAME}) "
    "manifest are present, which is not read yet"
)


def declared_ecosystems(app_dir: Path) -> list[str]:
    """Return every packaging ecosystem this app declares, in a stable order."""
    found = [PYPI] if manifests_present(app_dir) else []
    return found + ([NPM] if npm_manifest.has_manifest(app_dir) else [])


def dependencies_readable(app_dir: Path) -> tuple[bool, str]:
    """Say whether this repository's dependencies can be read, and why not if they cannot.

    A repository declaring two is refused rather than half-read. One SBOM holds
    one ecosystem, so reporting only the Python half would understate the tree
    while looking complete.
    """
    if not syft_runner.is_available():
        return False, f"{syft_runner.GENERATOR_NAME} is not installed"
    ecosystems = declared_ecosystems(app_dir)
    if len(ecosystems) > 1:
        return False, MIXED_MANIFEST_REASON
    if not ecosystems:
        return False, "no dependency manifest found"
    return True, ""


def _declarations(app_dir: Path, ecosystem: str) -> tuple[dict[str, str], list[str]]:
    """Return what the app declares and which manifests said so, for one ecosystem."""
    if ecosystem == PYPI:
        return read_requirements(app_dir), manifests_present(app_dir)
    return npm_manifest.read_manifest(app_dir), npm_manifest.manifests_present(app_dir)


def dependency_artifacts(app_dir: Path, surfaces: list[Surface],
                         ecosystem: str) -> tuple[dict[str, str], dict]:
    """Build the bill of materials and the surface-to-component mapping.

    Two bills are written. sbom.json is the contract the later phases read;
    sbom.cyclonedx.json is the same scan in a standard format, so the result
    can be fed to other supply-chain tooling and checked independently.
    """
    scanned = syft_runner.scan(app_dir)
    declared, present = _declarations(app_dir, ecosystem)
    document = build_sbom(
        scanned, declared,
        syft_runner.GENERATOR_NAME, syft_runner.generator_version(),
        present, syft_runner.GUESS_UNPINNED, ecosystem,
    )
    mapped = build_mapping(surfaces, document, local_module_names(str(app_dir)))
    return {
        SBOM_NAME: sbom_to_json(document),
        CYCLONEDX_NAME: sbom_to_json(to_cyclonedx(scanned)),
        MAPPING_NAME: mapping_to_json(mapped),
    }, mapped
