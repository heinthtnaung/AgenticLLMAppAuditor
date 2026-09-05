"""The executable record of the one absence a narrowing can still cause, as a strict xfail.

Task 7.4's headline invariant is rule 1: **a check the model does not name runs
on everything, and no absence from `coverage.checks_run` is ever the model's
doing.** `docs/SCHEMAS.md` defines an absence there as "could not look at all"
and `src/evaluation/scorer.py` reads it as `no_check_for_risk_class`, so an
absence the model caused is a coverage claim written by a model -- which
`docs/PHASE_7_PLAN.md` rejects as a contract violation rather than a preference.

One case still does it. `semantic_probe` runs at the edge, and `run_checks`
names it in `checks_run` only when it produced a probe. Narrowed to surfaces
with no prompt template among them it produces none, so it drops out -- and the
resulting document is byte-identical in its coverage claim to one from an app
that has no prompt template at all. Measured, both states:

    away from every template   in checks_run: False   checks_narrowed: []
    app with no template       in checks_run: False   checks_narrowed: []

**Why this is not the same as `high_privilege_tool` finding no tool.** A graph
check is appended to `checks_run` by `workflow.act` the moment it is dispatched,
so narrowing it to surfaces it cannot act on leaves it present, silent, and
carrying its narrowing record. Measured on the same shape: handed one data
source, `high_privilege_tool` reports `examined 1 of 3`, stays in `checks_run`
and finds nothing. Identical situation, two different artifacts -- because
`checks_run` means "was dispatched" for a graph check and "found a subject and
got an answer" for the edge check. That asymmetry predates this task; task 7.4
is what let a model move the probe from one state to the other.

**What is not wrong, so nobody re-argues it.** Making the probe unconditionally
present would undo 7.3, where `_probe_run` keying on "did a probe exist" was one
of seven defects found across two review rounds: a run whose every model call was
refused wrote `status: "used"` and named the model. And it would put the probe in
`checks_run` on an app with no template, which is the (correct) absence every
other check follows. The fix is to tell the two absences apart -- "no template in
this repo" from "templates here, narrowed away from all of them" -- which needs
the unnarrowed template count at the edge and is its own task, not a clause
bolted onto 7.4.

**What it costs today, stated so it is not overstated.** Nothing reaches the
scorer: `semantic_probe.OWASP_ID` is LLM01 and so is `taint`'s, and the probe
walks `python_files` just as the taint trace does -- so on every app where the
probe could contribute anything, taint ran too and LLM01 is in
`risk_classes_checked` regardless. This is an honesty defect in `findings.json`,
not a measured recall loss. The narrowing does stay recoverable from
`planner.json`'s `surface_selection`, which
`test_semantic_probe_narrowing.py` pins.

The test below is `xfail(strict=True)`: it states what the rule requires, and it
will fail the moment the code starts meeting it, which is what retires this file.
"""

import json

import pytest

from checks.run_checks import build_findings
from checks.semantic_probe import CHECK_NAME as PROBE_CHECK
from semantic_probe_fixtures import (
    PROBE_MODEL, PROMPT_SURFACE_ID, Answering, app_and_surfaces)

# Named once, so a reader chasing a strict-xfail failure is sent somewhere that
# explains it rather than to a bare test name.
MODEL_CAUSED_ABSENCE = (
    "a probe narrowed away from every prompt template leaves coverage.checks_run, "
    "which docs/SCHEMAS.md defines as 'could not look at all' -- an absence rule 1 "
    "says the model may never cause")


def audited(tmp_path, reply: str) -> dict:
    """Audit the one-template app with a stand-in model answering one fixed reply."""
    repo, surfaces = app_and_surfaces(tmp_path)
    document, _planner = build_findings(str(repo), surfaces, None, None, None,
                                        Answering(reply), PROBE_MODEL)
    return document


def narrowed_away_from_the_template(tmp_path) -> dict:
    """Audit with the probe narrowed to every surface except the app's one template."""
    repo, surfaces = app_and_surfaces(tmp_path)
    others = [surface.id for surface in surfaces if surface.id != PROMPT_SURFACE_ID]
    reply = json.dumps({"surfaces": {PROBE_CHECK: others}})
    document, _planner = build_findings(str(repo), surfaces, None, None, None,
                                        Answering(reply), PROBE_MODEL)
    return document


def test_the_unnarrowed_run_names_the_probe_in_checks_run(tmp_path) -> None:
    """Guard: without this the xfail below could pass by the probe never being there."""
    document = audited(tmp_path, "VULNERABLE: the template interpolates a value.")
    assert PROBE_CHECK in document["coverage"]["checks_run"]


@pytest.mark.xfail(strict=True, reason=MODEL_CAUSED_ABSENCE)
def test_a_narrowing_never_removes_a_check_from_checks_run(tmp_path) -> None:
    """Rule 1, stated for the one check that still breaks it.

    The app is unchanged and its template is still there; the only difference
    from the guard above is what the model asked for. So the absence is the
    model's doing, and that is the thing the whole phase forbids.
    """
    assert PROBE_CHECK in narrowed_away_from_the_template(tmp_path)["coverage"]["checks_run"]
