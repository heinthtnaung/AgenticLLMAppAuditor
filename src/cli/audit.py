"""One audit, end to end: scan, join, score, and gather the record.

Nothing here decides anything. Every step is a package that was built and tested
on its own, and this is the order they go in -- which is why the file is short
and why it is the only place that knows the order.

**The scanner versions are asked, not configured.** A provenance field somebody
types is a claim nobody checked, and the one purpose of that field is to make a
run checkable. This is how a report came to print `trivy 0.58.1` on a machine
running 0.74.0 while nothing was wrong with the report.
"""

import sys
from dataclasses import replace
from pathlib import Path
from typing import TextIO

from council.escalation_setting import escalation_model
from council.member_setting import council_members
from council.ollama import PINNED_SEED, PINNED_TEMPERATURE, PINNED_THINKING
from council.settings import current_settings
from deps import manifests, syft_runner, trivy_runner
from deps.trivy_database import DatedDatabase
from findings.finding import build_findings
from report.absences import Coverage
from report.provenance import AdvisoryDatabase, LocalModels, RunProvenance
from report.record import Report, build_report

from cli.arguments import Options
from cli.council_run import ORDER_CHECK, assessments, build_roster, escalation_member, watching
from cli.explanation_run import explainer_of, explaining, explanations
from cli.organisation_run import organisation_of, weigh_findings


def run_audit(
    options: Options, database: DatedDatabase, progress_to: TextIO = sys.stderr
) -> Report:
    """Scan one repository against the pinned database and gather everything into a record."""
    # Read first, like the walk below: a bad setting stops the run before the scan.
    options = members_asked_for(options)
    local = local_models_of(options)
    # Walked first: a directory nobody can list stops the run before the scan.
    unread = manifests.unread_manifests(options.repository)
    catalogue = syft_runner.scan_directory(options.repository)
    scanned = trivy_runner.scan_directory(options.repository, database.cache)
    findings = build_findings(catalogue.components, scanned.advisories)
    council = council_of(findings, options, progress_to, local)
    # Only once every value the council and escalation produce is in, for every finding.
    explained = explanations_of(findings, options, progress_to, local)
    answers, approval = organisation_of(options.answers)
    return build_report(
        provenance=provenance_of(options.repository, database.built_at, local),
        catalogue=catalogue,
        findings=findings,
        advisories_by_purl=scanned.advisories,
        secrets=scanned.secrets,
        council=council,
        risk=weighed(findings, answers, options),
        approval=approval,
        overridden=tuple(answers.by_advisory),
        coverage=coverage_of(options, unread),
        explanations=explained,
    )


def coverage_of(options: Options, unread: tuple[str, ...]) -> Coverage:
    """Say what the operator asked this run for, and which manifests it could read nothing from."""
    return Coverage(
        answers_given=options.answers is not None,
        council_named=bool(options.council_models),
        unread_manifests=unread,
    )


def provenance_of(
    repository: Path, database_built_at: str, local: LocalModels | None
) -> RunProvenance:
    """Record what produced this run, asking each tool its own version."""
    return RunProvenance(
        repository=str(repository),
        syft_version=syft_runner.installed_version(),
        trivy_version=trivy_runner.installed_version(),
        database=AdvisoryDatabase(built_at=database_built_at),
        local_models=local,
    )


def members_asked_for(options: Options) -> Options:
    """Give `--council` the members the settings name; any other run keeps the ones it was given."""
    # Read here and only here, so a `.env` naming members starts no model call on its own.
    if not options.council_from_settings:
        return options
    return replace(options, council_models=council_members())


def local_models_of(options: Options) -> LocalModels | None:
    """Say how every local member will be asked, or nothing, for a run that names none."""
    # Read only once a flag has named members: a setting alone never starts a council.
    if not options.council_models:
        return None
    chosen = current_settings()
    return LocalModels(
        server=chosen.server,
        context_tokens=chosen.context_tokens,
        timeout_seconds=chosen.timeout_seconds,
        temperature=PINNED_TEMPERATURE,
        seed=PINNED_SEED,
        think=PINNED_THINKING,
        order_check=ORDER_CHECK,
        escalation_model=escalation_model(),
    )


def weighed(findings, answers, options: Options):
    """Score the findings against this environment, or none when nobody answered."""
    if options.answers is None:
        return ()
    return weigh_findings(findings, answers)


def council_of(findings, options: Options, progress_to: TextIO, local: LocalModels | None):
    """Put the council to the findings that need one, or run none, which is the default."""
    # `local` is None exactly when no member was named, which is when no council runs.
    if local is None:
        return ()
    every = options.council_all_findings
    roster = build_roster(options.council_models)
    watcher = watching(findings, roster, progress_to, every)
    escalation = escalation_member(local.escalation_model)
    return assessments(
        findings, roster, progress=watcher, every_finding=every, escalation=escalation
    )


def explanations_of(findings, options: Options, progress_to: TextIO, local: LocalModels | None):
    """Ask why the sources differ on each disputed finding, or ask nothing where no council ran."""
    if local is None:
        return ()
    roster = build_roster(options.council_models)
    explainer = explainer_of(roster, escalation_member(local.escalation_model))
    return explanations(findings, explainer, progress=explaining(findings, progress_to))
