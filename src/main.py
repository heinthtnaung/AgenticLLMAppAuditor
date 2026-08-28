"""Command line entry point: audit one repository and write what was found.

What can be produced depends on what is available. The surfaces and the AI
inventory need nothing but the source; the bill of materials needs an external
generator and a dependency manifest this project knows how to read. Producing
less is a normal outcome and is reported, not treated as a failure.
"""

import argparse
import subprocess
import sys
from pathlib import Path

from artifacts.aibom import aibom_to_json, build_aibom
from artifacts.findings_document import findings_to_json
from artifacts.cyclonedx import to_cyclonedx
from artifacts.mapping import build_mapping, mapping_to_json
from artifacts.sbom import build_sbom, sbom_to_json
from artifacts.skipped_file import SkippedFile
from artifacts.surface import Surface, surfaces_to_json
from checks.run_checks import build_findings
from deps import npm_manifest, syft_runner
from deps.package_names import NPM, PYPI
from deps.requirements_parser import (
    MANIFEST_NAME as PYPI_MANIFEST_NAME,
    manifests_present,
    read_requirements,
)
from parsing.extractor import extract_repo
from parsing.repo_loader import local_module_names

DEFAULT_ARTIFACTS_DIR = Path("artifacts")

SURFACES_NAME = "surfaces.json"
AIBOM_NAME = "aibom.json"
SBOM_NAME = "sbom.json"
CYCLONEDX_NAME = "sbom.cyclonedx.json"
MAPPING_NAME = "mapping.json"
FINDINGS_NAME = "findings.json"

# Naming both files, not just both ecosystems: the reader has to know which two
# manifests to look at to understand why no bill was produced.
MIXED_MANIFEST_REASON = (
    f"both a Python ({PYPI_MANIFEST_NAME}) and an npm ({npm_manifest.MANIFEST_NAME}) "
    "manifest are present, which is not read yet"
)


# Conditions the user can fix, reported as a message rather than a traceback.
EXPECTED_FAILURES = (FileNotFoundError, NotADirectoryError, ValueError, RuntimeError)


def build_parser() -> argparse.ArgumentParser:
    """Describe the command line arguments."""
    parser = argparse.ArgumentParser(description="Audit an LLM application's source.")
    parser.add_argument("repo_path", help="path to the repository to analyse")
    parser.add_argument(
        "--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS_DIR,
        help=f"where to write the artifacts (default: {DEFAULT_ARTIFACTS_DIR})",
    )
    return parser


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


def report_skipped_files(skipped: list[SkippedFile]) -> None:
    """Warn about each file the scan could not analyse."""
    for record in skipped:
        where = f" (line {record.line})" if record.line else ""
        print(f"warning: skipped {record.file}: {record.reason}{where}", file=sys.stderr)


def report_coverage(mapping_document: dict) -> None:
    """Say how much of the app the mapping reached.

    Printed rather than stored: a mapping covering a third of the surfaces
    looks the same on disk as one covering all of them.
    """
    total, mapped = mapping_document["surface_count"], mapping_document["mapped_count"]
    share = f"{mapped / total:.0%}" if total else "n/a"
    print(f"  mapped {mapped} of {total} surfaces ({share})", file=sys.stderr)
    for reason, count in sorted(mapping_document["reason_counts"].items()):
        if count:
            print(f"    {reason:22} {count}", file=sys.stderr)
    for name in mapping_document["undeclared_components"]:
        print(f"  used but never declared: {name}", file=sys.stderr)


def run(args: argparse.Namespace) -> int:
    """Audit the repository and write its artifacts. Returns the exit code."""
    app_dir = Path(args.repo_path)
    scan = extract_repo(args.repo_path)
    report_skipped_files(scan.skipped)
    documents = {
        SURFACES_NAME: surfaces_to_json(scan.surfaces, scan.skipped),
        AIBOM_NAME: aibom_to_json(build_aibom(scan.surfaces)),
    }

    readable, no_bill_reason = dependencies_readable(app_dir)
    mapping_document = None
    if readable:
        built, mapping_document = dependency_artifacts(
            app_dir, scan.surfaces, declared_ecosystems(app_dir)[0])
        documents.update(built)

    documents[FINDINGS_NAME] = findings_to_json(
        build_findings(args.repo_path, scan.surfaces, mapping_document))

    out = args.artifacts_dir / app_dir.resolve().name
    out.mkdir(parents=True, exist_ok=True)
    for name, text in sorted(documents.items()):
        (out / name).write_text(text, encoding="utf-8")
    print(f"wrote {len(documents)} artifacts to {out}")

    if no_bill_reason:
        print(f"  no bill of materials: {no_bill_reason}", file=sys.stderr)
    if mapping_document is not None:
        report_coverage(mapping_document)
    return 0


def main() -> int:
    """Audit a repository. Returns the process exit code."""
    args = build_parser().parse_args()
    try:
        return run(args)
    except (*EXPECTED_FAILURES, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
