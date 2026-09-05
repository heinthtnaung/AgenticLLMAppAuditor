"""The edge check and the narrowing: what `checks_narrowed` says it examined, it examined.

`semantic_probe` is the one narrowable check that does **not** run inside the
graph, so `workflow.act`'s filter never reaches it. It is also the check most
worth narrowing, because it costs one model call per prompt template -- which is
why `run_checks` now applies `surfaces_for` to the edge call rather than the
probe being dropped from `NARROWABLE_CHECKS`.

**What `examined_surface_count` counts, settled here because it was ambiguous.**
It is the surfaces *handed to* the check, not the subjects the check found among
them. The denominator proves it: `eligible_surface_count` is the whole run's
surface count for every check, whatever kinds that check acts on -- so
`high_privilege_tool` handed three surfaces of which one is a tool reports three
of three and no narrowing at all. A count of subjects would put those two
numbers in different units and make `examined <= eligible` true for reasons
having nothing to do with narrowing. The test below pins it with a narrowing
that keeps the template: two surfaces handed over, one probe produced.

**One thing this file does not assert, and `test_narrowing_defect.py` says why.**
A probe narrowed away from every template produces no probe, so it is absent
from `coverage.checks_run` -- which is a model-caused absence, and rule 1 says
there is no such thing. That gap is a strict xfail in its own file rather than a
weakened assertion here.
"""

import json

from artifacts.surface import TOOL_CALL
from checks.run_checks import build_findings
from checks.semantic_probe import CHECK_NAME as PROBE_CHECK
from semantic_probe_fixtures import (
    PROBE_MODEL, PROMPT_SURFACE_ID, Answering, app_and_surfaces)

# A reply that names one surface for the probe, and it is deliberately not the
# prompt template: the template is the only thing the probe has to say anything
# about, so a narrowing that excluded it and was applied would produce no probe.
NARROWING_REPLY_TEMPLATE = '{"surfaces": {"%s": ["%s"]}}'


def audit_narrowed_away_from_the_template(tmp_path) -> tuple[dict, dict]:
    """Audit the prompt app with the probe narrowed to a surface that is not the template."""
    repo, surfaces = app_and_surfaces(tmp_path)
    other = next(surface.id for surface in surfaces if surface.id != PROMPT_SURFACE_ID)
    reply = NARROWING_REPLY_TEMPLATE % (PROBE_CHECK, other)
    return build_findings(str(repo), surfaces, None, None, None,
                          Answering(reply), PROBE_MODEL)


def test_the_reply_this_file_sends_is_a_narrowing_of_the_probe(tmp_path) -> None:
    """Guard: a reply the guard refused would make the two tests below prove nothing."""
    _document, planner_document = audit_narrowed_away_from_the_template(tmp_path)
    selection = planner_document["surface_selection"]
    assert PROBE_CHECK in selection
    assert PROMPT_SURFACE_ID not in selection[PROBE_CHECK]


def test_the_probe_only_examines_the_surfaces_it_was_narrowed_to(tmp_path) -> None:
    """The claim `findings.json` makes about this run, checked against the probes it holds.

    The probe records name the surfaces the check actually looked at. Narrowed
    away from the template, it must not have probed the template -- and if it
    did, the narrowing was recorded and never applied.
    """
    document, planner_document = audit_narrowed_away_from_the_template(tmp_path)
    selected = set(planner_document["surface_selection"][PROBE_CHECK])
    probed = {probe["subject_id"] for probe in document["probes"]}
    assert probed <= selected


def narrowed_keeping_the_template(tmp_path) -> tuple[dict, dict]:
    """Audit with the probe narrowed to the template and one other surface.

    Two of the app's three surfaces, and the template is one of them -- so the
    check is handed two surfaces and finds one subject among them. That gap
    between two and one is what makes the count's meaning testable.
    """
    repo, surfaces = app_and_surfaces(tmp_path)
    tool = next(surface.id for surface in surfaces if surface.kind == TOOL_CALL)
    reply = json.dumps({"surfaces": {PROBE_CHECK: [PROMPT_SURFACE_ID, tool]}})
    return build_findings(str(repo), surfaces, None, None, None,
                          Answering(reply), PROBE_MODEL)


def test_the_published_count_is_the_surfaces_handed_over_not_the_subjects_found(
        tmp_path) -> None:
    """Two surfaces handed to the check, one prompt template among them, and the count is two.

    Written as an inequality against the probe count on purpose: `[2]` alone
    could be satisfied by a count of subjects on some other app, but two
    handed over beside one probed can only be satisfied by the handed-to
    reading. `docs/SCHEMAS.md` says "how many surfaces it actually examined",
    which is loose enough to have caused this exact confusion once already.
    """
    document, _planner = narrowed_keeping_the_template(tmp_path)
    assert document["probe_count"] == 1
    assert [entry["examined_surface_count"] for entry in document["checks_narrowed"]
            if entry["check"] == PROBE_CHECK] == [2]


def test_a_narrowing_that_keeps_a_subject_leaves_the_check_in_checks_run(tmp_path) -> None:
    """It looked and it answered, so it is named -- the record qualifies the name."""
    document, _planner = narrowed_keeping_the_template(tmp_path)
    assert PROBE_CHECK in document["coverage"]["checks_run"]


def test_a_probe_narrowed_away_from_every_template_publishes_no_narrowing(
        tmp_path) -> None:
    """The record goes because the check does: `check_narrowings` refuses one without the other.

    Handed two surfaces and no prompt template among them, the probe produces
    nothing, so it is absent from `checks_run` -- and a narrowing record naming
    a check that is not in `checks_run` is the contradiction the coverage
    validator raises on. Consistent, and the honesty this costs is the subject
    of `test_narrowing_defect.py`.
    """
    document, _planner = audit_narrowed_away_from_the_template(tmp_path)
    assert document["checks_narrowed"] == []
    assert PROBE_CHECK not in document["coverage"]["checks_run"]


def test_the_narrowing_is_still_recoverable_from_the_planner_artifact(tmp_path) -> None:
    """`findings.json` loses the fact; `planner.json` must not, or the run is unrecorded.

    This is the whole mitigation for the gap above. The narrowing was honoured
    rather than refused, so it sits in `surface_selection` -- and that file is
    the only place a reader can learn the model narrowed this check to nothing
    useful.
    """
    _document, planner_document = audit_narrowed_away_from_the_template(tmp_path)
    assert PROMPT_SURFACE_ID not in planner_document["surface_selection"][PROBE_CHECK]
    assert planner_document["refused_narrowing"] == []
