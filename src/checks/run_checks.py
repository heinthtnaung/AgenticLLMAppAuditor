"""Runs every static check over one app's artifacts and assembles findings.json.

Kept out of main.py, which is the command line and already at its size. The
checks themselves live one per module; this decides which run and records what
they covered.
"""

from pathlib import Path

from artifacts.finding import Finding, Probe
from artifacts.findings_document import (
    MODEL_DISABLED,
    build_findings_document,
    coverage,
    model_run,
)
from artifacts.surface import Surface
from checks import permissions, supply_chain, taint, workflow
from artifacts.skipped_file import UnreadableSource
from parsing.extractor_python import parse_file
from parsing.languages import PYTHON, language_of
from parsing.repo_loader import list_source_files

# Every check this module knows how to run. `coverage.checks_run` reports the
# ones that actually examined something on this app, which is not the same
# list: a check named there but silent means "looked, found nothing", so a
# check that could not look at all must be absent rather than silent.
CHECK_NAMES = (supply_chain.CHECK_NAME, permissions.CHECK_NAME, taint.CHECK_NAME)


def run_static_checks(surfaces: list[Surface], mapping_document: dict | None) -> list[Finding]:
    """Run every static check. A missing mapping silences the checks that need one."""
    found = list(permissions.find_over_privileged_tools(surfaces))
    if mapping_document is not None:
        found += supply_chain.find_undeclared_dependencies(
            mapping_document, supply_chain.surface_fields(surfaces))
    return found


def build_findings(repo_path: str, surfaces: list[Surface],
                   mapping_document: dict | None) -> dict:
    """Return the findings document for one app.

    The planner decides the order and records what it ran, so
    `coverage.checks_run` is what the workflow actually did rather than a list
    written by hand beside it.

    The model is not used yet: these checks read artifacts and report what they
    find, so there is no prose to write. `model_run.status` says `disabled`
    rather than leaving a reader to guess why every narrative is null.
    """
    planned = _checks_that_examined_something(repo_path, mapping_document)
    state = workflow.audit(repo_path, surfaces, mapping_document, planned)
    return build_findings_document(
        state["findings"], state["probes"],
        coverage(len(surfaces), state["checks_run"]),
        model_run(MODEL_DISABLED),
    )


def _checks_that_examined_something(repo_path: str, mapping_document: dict | None) -> list[str]:
    """Name only the checks with something to look at on this app.

    A check listed here and silent means it looked and found nothing. One that
    could not look -- no mapping to read, or no Python to trace -- is left out,
    because listing it would report a clean result it never established.
    """
    ran = [permissions.CHECK_NAME]
    if mapping_document is not None:
        ran.append(supply_chain.CHECK_NAME)
    if taint.python_files(repo_path):
        ran.append(taint.CHECK_NAME)
    return ran
