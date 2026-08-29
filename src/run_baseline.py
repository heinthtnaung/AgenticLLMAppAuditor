"""Runs one baseline system over the corpus and writes the artifacts a score needs.

Separate from `main.py`, which runs the auditor, and from `evaluate.py`, which
reads what either produced. A baseline writes exactly the two files the scorer
opens -- `findings.json` and `surfaces.json` -- into its own system directory, so
the harness scores it unmodified and no system can overwrite another's output.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from artifacts.findings_document import (
    MODEL_DISABLED,
    build_findings_document,
    coverage,
    findings_to_json,
    model_run,
)
from artifacts.surface import surfaces_to_json
from baselines import sbom_only, static_rules
from baselines.rules import RULES
from corpus_paths import DOWNLOAD_HINT, app_is_present, app_path, discover_corpus_apps

DEFAULT_ARTIFACTS_DIR = Path("artifacts")
FINDINGS_NAME = "findings.json"
SURFACES_NAME = "surfaces.json"

STATIC_RULES = "baseline_static_rules"
SBOM_ONLY = "baseline_sbom_only"
BASELINES = (STATIC_RULES, SBOM_ONLY)

EXPECTED_FAILURES = (FileNotFoundError, NotADirectoryError, ValueError, RuntimeError)


def build_parser() -> argparse.ArgumentParser:
    """Describe the command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run one baseline system over the corpus, for comparison against the auditor.")
    parser.add_argument("system", choices=BASELINES, help="which baseline to run")
    parser.add_argument(
        "--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS_DIR,
        help=f"root the system directory is written under (default: {DEFAULT_ARTIFACTS_DIR})",
    )
    return parser


@dataclass(frozen=True)
class BaselineRun:
    """One baseline's whole result for one app, so four lists cannot be unpacked wrongly."""

    findings: list
    surfaces: list
    checks: list[str]
    # The classes the checks above CAN report, not the ones they happened to
    # report. Deriving these from the findings would make a silent rule look
    # like an absent one, which is an error in the baseline's own favour.
    risk_classes: list[str]
    skipped: list


def _static_rules_documents(repo_path: str) -> BaselineRun:
    """Run Baseline A: findings, the surfaces they named, the rules, and what it could not read."""
    findings = static_rules.scan_repo(repo_path)
    return BaselineRun(
        findings, static_rules.surfaces_from(findings), list(static_rules.CHECK_NAMES),
        sorted({rule.owasp_id for rule in RULES}), static_rules.unreadable_files(repo_path),
    )


def _sbom_only_documents(repo_path: str) -> BaselineRun:
    """Run Baseline B: component findings, no surfaces at all, one check."""
    findings = sbom_only.scan_repo(repo_path)
    ran = bool(findings)
    return BaselineRun(findings, [], [sbom_only.CHECK_NAME] if ran else [],
                       [sbom_only.OWASP_ID] if ran else [], [])


BUILDERS = {STATIC_RULES: _static_rules_documents, SBOM_ONLY: _sbom_only_documents}


def build_documents(system: str, repo_path: str) -> tuple[str, str]:
    """Return one app's findings.json and surfaces.json for one baseline, as text."""
    run = BUILDERS[system](repo_path)
    findings, surfaces, checks, risk_classes, skipped = (
        run.findings, run.surfaces, run.checks, run.risk_classes, run.skipped)
    document = build_findings_document(
        findings, [],
        # No mapping was built, so the count is null rather than 0: this system
        # never had components to resolve, which is not the same as resolving
        # them all.
        coverage(len(surfaces), checks, risk_classes_checked=risk_classes,
                 unresolved_component_count=None),
        model_run(MODEL_DISABLED),
    )
    return findings_to_json(document), surfaces_to_json(surfaces, skipped)


def write_app(system: str, app: str, artifacts_dir: Path) -> Path:
    """Write one app's two artifacts under the baseline's own system directory."""
    out = artifacts_dir / system / app
    out.mkdir(parents=True, exist_ok=True)
    findings_json, surfaces_json = build_documents(system, str(app_path(app)))
    (out / FINDINGS_NAME).write_text(findings_json, encoding="utf-8")
    (out / SURFACES_NAME).write_text(surfaces_json, encoding="utf-8")
    return out


def run(args: argparse.Namespace) -> int:
    """Run one baseline over every downloaded fixture. Returns the process exit code."""
    apps = discover_corpus_apps()
    absent = [app for app in apps if not app_is_present(app)]
    if absent:
        raise FileNotFoundError(f"cannot run {args.system} over {', '.join(absent)}: {DOWNLOAD_HINT}")

    for app in apps:
        out = write_app(args.system, app, args.artifacts_dir)
        print(f"{args.system}: wrote {out}")
    print(f"ran {args.system} over {len(apps)} apps; score it with "
          f"`python src/evaluate.py --system {args.system}`")
    return 0


def main() -> int:
    """Run a baseline. Returns the process exit code."""
    args = build_parser().parse_args()
    try:
        return run(args)
    except EXPECTED_FAILURES as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
