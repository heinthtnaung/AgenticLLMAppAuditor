"""Command line entry point: audit one repository and write what was found.

What can be produced depends on what is available. The surfaces and the AI
inventory need nothing but the source; the bill of materials needs an external
generator and a dependency manifest this project knows how to read. Producing
less is a normal outcome and is reported, not treated as a failure.
"""

import argparse
import time
import subprocess
import sys
from pathlib import Path

from artifacts.aibom import aibom_to_json, build_aibom
from artifacts.findings_document import findings_to_json
from artifacts.planner_document import planner_to_json
from artifacts.surface import surfaces_to_json
from checks.run_checks import build_findings
from deps.inputs import (
    declared_ecosystems, dependencies_readable, dependency_artifacts)
from deps import trivy_runner
from parsing.extractor import extract_repo
from parsing.repo_loader import local_module_names
import model_client
import pipeline

import outputs
from outputs import (
    AIBOM_NAME,
    FINDINGS_NAME,
    SURFACES_NAME,
)

# The auditor is one of three scored systems, so its artifacts live under its
# own name: a baseline's findings.json must not overwrite the auditor's. The
# literal is deliberately not imported from `evaluation.document` -- that keeps
# the evaluation package out of the auditor's imports, since the tool being
# scored should not reach into the thing scoring it. A test asserts the two
# agree, so the copy cannot drift.
DEFAULT_ARTIFACTS_DIR = Path("artifacts") / "agentic_auditor"


# Conditions the user can fix, reported as a message rather than a traceback.
EXPECTED_FAILURES = (FileNotFoundError, FileExistsError, NotADirectoryError,
                     ValueError, RuntimeError)


def build_parser() -> argparse.ArgumentParser:
    """Describe the command line arguments."""
    parser = argparse.ArgumentParser(description="Audit an LLM application's source.")
    parser.add_argument("repo_path", help="path to the repository to analyse, or an "
                        "https:// link to fetch, audit, and publish in one run")
    parser.add_argument(
        "--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS_DIR,
        help=f"where to write the artifacts (default: {DEFAULT_ARTIFACTS_DIR})",
    )
    parser.add_argument(
        "--semantic-probe", action="store_true",
        help="ask the local model to judge each prompt template for injection. "
             "Off by default: it puts model-authored findings in findings.json, "
             "which is otherwise byte-identical whether a model ran or not. It "
             "is also the switch that lets the model choose the check order, "
             "recorded in planner.json",
    )
    return parser


def probe_inputs(wanted: bool) -> tuple[object, dict | None]:
    """The model call and its provenance for the semantic probe, or nothing.

    The one place an audit hands `model_client.ask` to a check. Imported here
    rather than in `checks/semantic_probe.py`, which
    `tests/parsing/test_offline_containment.py` bars from naming the module at
    all -- the check stays pure and the socket stays at the edge.
    """
    if not wanted:
        return None, None
    try:
        digest = model_client.model_digest()
    except RuntimeError:
        # The digest is a provenance nicety; the audit is not. Asking for it
        # unguarded meant `--semantic-probe` with the server down wrote **no
        # artifacts at all** -- and every degradation path the probe has was
        # unreachable through the command line. `outputs.build_remediation`
        # guards the same call for the same reason.
        digest = None
    return model_client.ask, {
        "identifier": model_client.MODEL,
        "settings": model_client.DECODE_SETTINGS,
        "digest": digest,
    }


def advisory_inputs(app_dir: Path) -> tuple[dict | None, dict | None]:
    """Trivy's advisories indexed for the join, and the pin naming what matched.

    (None, None) degrades exactly as a missing Syft does: the check is absent
    from checks_run and coverage says advisory_data was not ingested.
    """
    date = trivy_runner.db_snapshot_date() if trivy_runner.is_available() else None
    if date is None:
        return None, None
    report = trivy_runner.scan(app_dir)
    return trivy_runner.advisory_index(report), trivy_runner.pin(report, date)


def run(args: argparse.Namespace) -> int:
    """Audit the repository and write its artifacts. Returns the exit code.

    Times itself: "audit execution time" is one of the measures the proposal
    committed to, and a wall-clock second is the only honest unit here -- the
    run shells out to Syft and Trivy and may call a local model, so CPU time
    would understate what a reader actually waits for.
    """
    started = time.monotonic()
    app_dir = pipeline.resolve_repo(args.repo_path)
    scan = extract_repo(str(app_dir))
    outputs.report_skipped_files(scan.skipped)
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

    advisories, advisory_pin = ((None, None) if mapping_document is None
                                else advisory_inputs(app_dir))
    findings_document, planner_document = build_findings(
        str(app_dir), scan.surfaces, mapping_document, advisories, advisory_pin,
        *probe_inputs(args.semantic_probe))
    documents[FINDINGS_NAME] = findings_to_json(findings_document)
    documents[outputs.PLANNER_NAME] = planner_to_json(planner_document)
    documents.update(outputs.standard_format(findings_document))
    # The only model call an audit makes, and the only artifact it writes into.
    # findings.json is written above and never revisited, so the scored numbers
    # stay static whatever the model says.
    documents[outputs.REMEDIATION_NAME] = outputs.build_remediation(
        findings_document, outputs.declared_language(scan.surfaces),
        tuple(local_module_names(str(app_dir))))

    app = app_dir.resolve().name
    written = outputs.write_all(args.artifacts_dir / app, documents, app)
    print(f"wrote {written} artifacts to {args.artifacts_dir / app}")

    if no_bill_reason:
        print(f"  no bill of materials: {no_bill_reason}", file=sys.stderr)
    if mapping_document is not None:
        outputs.report_coverage(mapping_document)
    # A link runs the whole pipeline; a local path stays the offline audit.
    if pipeline.is_url(args.repo_path):
        pipeline.publish(args.artifacts_dir / app, advisory_pin is not None)
    # Printed, never written into an artifact: a duration is the one number here
    # that changes on every run, and putting it in a file would break the
    # byte-identical guarantee every artifact makes for a fact about the
    # machine rather than about the audited app.
    print(f"audit completed in {time.monotonic() - started:.2f} seconds")
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
