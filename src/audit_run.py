"""Runs one audit over one repository and writes its artifacts.

Split out of `main.py` when `--compare-models` landed: that flag audits the same
tree twice, once driven by the local model and once by a hosted one, and a body
that reads its model out of `argparse` cannot be run twice with two different
ones. So the model arrives as an argument here and the command line stays in
`main.py`.

**Nothing in this module chooses a model.** It is handed one, or handed nothing
and stays offline -- which is what keeps an ordinary audit's guarantee intact
now that a second network client exists in `src/`.
"""

import sys
import time
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
import fetch_repo
import model_client
import outputs
from reporting import progress
import remediation_run
from outputs import AIBOM_NAME, FINDINGS_NAME, SURFACES_NAME


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


def _dependency_documents(app_dir: Path, surfaces: list) -> tuple[dict, dict | None, str]:
    """The bill of materials and the surface-to-component mapping, when readable."""
    readable, no_bill_reason = dependencies_readable(app_dir)
    if not readable:
        return {}, None, no_bill_reason
    built, mapping_document = dependency_artifacts(
        app_dir, surfaces, declared_ecosystems(app_dir)[0])
    return built, mapping_document, no_bill_reason


def audit(app_dir: Path, artifacts_dir: Path, model: dict | None = None) -> dict:
    """Audit one tree and write its artifacts. Returns what the caller must report.

    `model` is `{"ask", "identifier", "settings", "digest"}` or None. None is an
    ordinary audit: no model call, no socket, and `findings.json` byte-identical
    to every previous run. One model drives the planner, the semantic probe and
    the advice, so an arm's artifacts name the model that actually produced them.
    """
    started = time.monotonic()
    scan = extract_repo(str(app_dir))
    progress.report_skipped_files(scan.skipped)
    documents = {
        SURFACES_NAME: surfaces_to_json(scan.surfaces, scan.skipped),
        AIBOM_NAME: aibom_to_json(build_aibom(scan.surfaces)),
    }
    built, mapping_document, no_bill_reason = _dependency_documents(app_dir, scan.surfaces)
    documents.update(built)

    advisories, advisory_pin = ((None, None) if mapping_document is None
                                else advisory_inputs(app_dir))
    probe = (model["ask"], _probe_provenance(model)) if model else (None, None)
    findings_document, planner_document = build_findings(
        str(app_dir), scan.surfaces, mapping_document, advisories, advisory_pin, *probe)
    documents[FINDINGS_NAME] = findings_to_json(findings_document)
    documents[outputs.PLANNER_NAME] = planner_to_json(planner_document)
    documents.update(outputs.standard_format(findings_document))
    # The only model call an audit makes beyond the planner and the probe, and
    # the only artifact it writes into. findings.json is written above and never
    # revisited, so the scored numbers stay static whatever the model says.
    documents[outputs.REMEDIATION_NAME] = remediation_run.build_remediation(
        findings_document, remediation_run.declared_language(scan.surfaces),
        tuple(local_module_names(str(app_dir))), model)

    app = app_dir.resolve().name
    written = outputs.write_all(artifacts_dir / app, documents, app)
    print(f"wrote {written} artifacts to {artifacts_dir / app}")
    if no_bill_reason:
        print(f"  no bill of materials: {no_bill_reason}", file=sys.stderr)
    if mapping_document is not None:
        progress.report_coverage(mapping_document)
    return {"app": app, "artifacts": artifacts_dir / app,
            "advisories_read": advisory_pin is not None,
            "seconds": time.monotonic() - started}


def local_model(wanted: bool = True) -> dict | None:
    """The local model and what an artifact should record about it, or None.

    Lives here because both entry points need it: `main` for an ordinary audit
    and `compare_run` for the local arm. Two copies of this dict in two modules
    had to agree, and nothing checked that they did.
    """
    if not wanted:
        return None
    try:
        digest = model_client.model_digest()
    except RuntimeError:
        # The digest is a provenance nicety; the audit is not. Asking for it
        # unguarded meant `--semantic-probe` with the server down wrote **no
        # artifacts at all**.
        digest = None
    return {"ask": model_client.ask, "identifier": model_client.MODEL,
            "settings": model_client.DECODE_SETTINGS, "digest": digest}


def _probe_provenance(model: dict) -> dict:
    """What the findings document records about the model that ran the probe."""
    return {"identifier": model["identifier"], "settings": model["settings"],
            "digest": model.get("digest")}


def report_pin_gap(app_dir: Path) -> None:
    """Say when a tree cannot be checked against the commit its manifest pins."""
    unchecked = fetch_repo.check_tree_matches_pin(app_dir)
    if unchecked:
        print(f"  {unchecked}", file=sys.stderr)
