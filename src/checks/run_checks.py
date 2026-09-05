"""Runs every static check over one app's artifacts and assembles findings.json.

Kept out of main.py, which is the command line and already at its size. The
checks themselves live one per module; this decides which run and records what
they covered.
"""

from artifacts.findings_document import (
    ADVISORY_NOT_INGESTED,
    ADVISORY_SNAPSHOT,
    MODEL_DISABLED,
    MODEL_UNAVAILABLE,
    MODEL_USED,
    build_findings_document,
    coverage,
    model_run,
)
from artifacts.finding import (
    CONFIRMED, INCONCLUSIVE, NOT_RUN, REFUTED, SCHEMA_VERSION, Probe)
from artifacts.planner_document import build_planner_document
from artifacts.surface import Surface
from checks import (
    auditability, known_advisory, output_handling, permissions, planner,
    semantic_probe, supply_chain, taint, workflow)
from checks.plan_selection import (
    NARROWABLE_CHECKS, narrowing_records, surfaces_for)

# Which OWASP class each check can report. The artifact carries the classes a
# run actually examined, so a scorer can tell "no check covers this risk" from
# "a check covered it and stayed silent" -- without importing this module and
# scoring a stale artifact against fresh code.
RISK_CLASS_BY_CHECK = {
    supply_chain.CHECK_NAME: supply_chain.OWASP_ID,
    permissions.CHECK_NAME: permissions.OWASP_ID,
    taint.CHECK_NAME: taint.OWASP_ID,
    known_advisory.CHECK_NAME: known_advisory.OWASP_ID,
    output_handling.CHECK_NAME: output_handling.OWASP_ID,
    auditability.CHECK_NAME: auditability.OWASP_ID,
    semantic_probe.CHECK_NAME: semantic_probe.OWASP_ID,
}

# Checks that run at the *edge* rather than inside the LangGraph loop, because
# they need the model and the graph must attempt no socket. They are in the map
# above -- their risk class still has to be declared -- but never in
# `workflow.KNOWN_CHECKS`, which is why the two are compared minus this set.
EDGE_CHECKS = (semantic_probe.CHECK_NAME,)

# Probe outcomes that mean the model actually answered. A run whose every call
# was refused produced probes but consulted nothing.
ANSWERED_OUTCOMES = (CONFIRMED, REFUTED)

# Graph-runnable checks, derived once here rather than subtracted inside three
# separate test assertions -- a subtraction written in a test is an invariant
# that can be weakened without anyone noticing.
GRAPH_CHECKS = tuple(name for name in RISK_CLASS_BY_CHECK if name not in EDGE_CHECKS)

if not NARROWABLE_CHECKS <= set(RISK_CLASS_BY_CHECK):
    raise ValueError(
        f"NARROWABLE_CHECKS names {sorted(NARROWABLE_CHECKS - set(RISK_CLASS_BY_CHECK))}, "
        "which this module cannot run")

# Every check this module knows how to run, taken from the map above so a check
# can never be planned without declaring the risk it covers. `coverage.checks_run`
# reports the ones that actually examined something on this app, which is not the
# same list: a check named there but silent means "looked, found nothing", so a
# check that could not look at all must be absent rather than silent.
CHECK_NAMES = tuple(RISK_CLASS_BY_CHECK)


def _planner_model(model_ask_fn: semantic_probe.Ask | None,
                   probe_model: dict | None) -> tuple[semantic_probe.Ask | None, str | None]:
    """The model call and identifier to plan with, or nothing at all.

    Both or neither: `order_checks` refuses an `ask` it cannot name, because a
    run that used a model without recording which one cannot be repeated.
    """
    if model_ask_fn is None or not probe_model:
        return None, None
    return model_ask_fn, probe_model["identifier"]


def _answered(probes: list[Probe]) -> bool:
    """Say whether the model replied at all, however unusably."""
    return any(probe.outcome in ANSWERED_OUTCOMES
               or (probe.outcome == INCONCLUSIVE and probe.reason == semantic_probe.NO_MODEL)
               for probe in probes)


def _probe_run(probe_model: dict | None, probes: list[Probe]) -> dict:
    """Say what produced the document's model-authored content, honestly.

    Three states, not two. `disabled` beside a model-authored finding would be
    a false provenance record in the artifact Phase 4 grades -- but so would
    `used` on a run where the server refused every connection, and a probe that
    records `model_unavailable` is still a probe. So the question is whether a
    call was *answered*, not whether a record was produced. `model_provenance`
    then requires a used run to name the model and the decode settings, which is
    what makes the verdict repeatable; `unavailable` names nothing, because
    there is nothing to name.
    """
    if not probes or not probe_model:
        return model_run(MODEL_DISABLED)
    if _answered(probes):
        return model_run(MODEL_USED, probe_model["identifier"],
                         probe_model["settings"], digest=probe_model.get("digest"))
    # `unavailable` is a claim that the server could not be reached, so it is
    # earned by a probe that actually tried. A run whose every template was
    # unreadable never placed a call, and saying "unavailable" there would be
    # the mirror of the bug this function already fixed once.
    if any(probe.outcome == NOT_RUN for probe in probes):
        return model_run(MODEL_UNAVAILABLE)
    return model_run(MODEL_DISABLED)


def build_findings(repo_path: str, surfaces: list[Surface],
                   mapping_document: dict | None,
                   advisories: dict | None = None,
                   advisory_pin: dict | None = None,
                   model_ask_fn: semantic_probe.Ask | None = None,
                   probe_model: dict | None = None) -> tuple[dict, dict]:
    """Return the findings document for one app.

    The planner decides the order and records what it ran, so
    `coverage.checks_run` is what the workflow actually did rather than a list
    written by hand beside it.

    Returns the findings document and the planner document beside it. The
    planner record is a separate artifact, not a block in `findings.json`: the
    order provably changes nothing else in that file, so carrying it there would
    spend the byte-identical guarantee for a value with no effect on it.

    Every static check runs inside the graph. The planner and `semantic_probe`
    run here, at the edge, because they need the model and the graph must
    attempt no socket -- and both are inert without `model_ask_fn`, so a default
    audit produces exactly the document it did before either existed.
    """
    planned = _checks_that_examined_something(
        repo_path, surfaces, mapping_document, advisories)
    # The model may reorder the plan and may never shorten it: `order_checks`
    # returns a permutation, so every eligible check still runs and no absence
    # from `coverage.checks_run` can be the model's doing.
    order, planner_record = planner.order_checks(
        surfaces, planned, *_planner_model(model_ask_fn, probe_model),
        selectable=planned + [name for name in EDGE_CHECKS if model_ask_fn is not None])
    selection = planner_record["surface_selection"]
    state = workflow.audit(repo_path, surfaces, mapping_document, order, advisories,
                           selection)
    # At the edge, outside the graph: `tests/parsing/test_offline.py` asserts
    # the graph *attempts* no socket, counting attempts rather than successes.
    # Absent a model this returns nothing at all, so the document is unchanged.
    # Narrowed here too: `surfaces_for` is applied inside `workflow.act`, which
    # an edge check never enters, so without this the probe would examine every
    # surface while `checks_narrowed` published a smaller count -- a false
    # statement in `findings.json` about the check most worth narrowing, since
    # it costs one model call per prompt template.
    probe_findings, probe_probes = semantic_probe.run_over_repo(
        repo_path,
        surfaces_for(semantic_probe.CHECK_NAME, selection, surfaces),
        model_ask_fn)
    # From what actually ran, not from the plan: the workflow can stop at
    # MAX_STEPS, and claiming a risk class no check reached inverts the whole
    # point of the field.
    # A check that produced no probe at all had nothing to look at -- no prompt
    # template, or no model offered -- so it is absent rather than silent, the
    # same rule every other check here follows.
    # Named only when it looked. Probes that all say `not_run` mean the one
    # instrument this check has was unreachable, and `docs/SCHEMAS.md` defines a
    # name in `checks_run` as "looked and found nothing" -- which the scorer
    # then reads as an ordinary miss rather than `no_check_for_risk_class`.
    looked = any(probe.outcome != NOT_RUN for probe in probe_probes)
    ran = state["checks_run"] + ([semantic_probe.CHECK_NAME] if looked else [])
    classes = sorted({RISK_CLASS_BY_CHECK[name] for name in ran})
    document = build_findings_document(
        state["findings"] + probe_findings, state["probes"] + probe_probes,
        coverage(len(surfaces), ran, risk_classes_checked=classes,
                 unresolved_component_count=supply_chain.unresolved_component_count(
                     mapping_document),
                 advisory_data=ADVISORY_SNAPSHOT if advisories is not None
                 else ADVISORY_NOT_INGESTED,
                 advisory_unreached_component_count=(
                     known_advisory.unreached_component_count(mapping_document, advisories)),
                 advisory_unreached_components=(
                     known_advisory.unreached_components(mapping_document, advisories)),
                 **(advisory_pin or {})),
        _probe_run(probe_model, probe_probes),
        # Only for checks that actually ran: a check narrowed away from every
        # subject it had produces nothing, so it is absent from `checks_run`,
        # and a narrowing record naming it would contradict that.
        [record for record in narrowing_records(selection, surfaces)
         if record["check"] in ran],
    )
    return document, build_planner_document(planner_record, SCHEMA_VERSION)


def _has_llm_surface(surfaces: list[Surface]) -> bool:
    """Say whether this app drives a model at all: an agent definition or a tool call."""
    return any(surface.kind in taint.SINK_KINDS for surface in surfaces)


def _checks_that_examined_something(repo_path: str, surfaces: list[Surface],
                                    mapping_document: dict | None,
                                    advisories: dict | None = None) -> list[str]:
    """Name only the checks with something to look at on this app.

    A check listed here and silent means it looked and found nothing. One that
    could not look is left out, because listing it would report a clean result
    it never established. Three things stop a check looking: no mapping to
    read, no Python to trace, and -- for a check scoped to LLM applications --
    no LLM surface anywhere in the repo.
    """
    has_python = bool(taint.python_files(repo_path))
    ran = [permissions.CHECK_NAME]
    if mapping_document is not None:
        ran.append(supply_chain.CHECK_NAME)
    if has_python:
        ran.append(taint.CHECK_NAME)
    # Both halves or nothing: advisories without a mapping have no reach to
    # join against, and would report a clean result never established.
    if mapping_document is not None and advisories is not None:
        ran.append(known_advisory.CHECK_NAME)
    # Scoped to LLM apps deliberately: the rule is CWE-89 with an LLM filter,
    # and firing it on a plain Python service would claim an LLM finding where
    # there is no model. No LLM surface means the check is absent rather than
    # silent, so LLM02 reads as unexamined.
    if has_python and _has_llm_surface(surfaces):
        ran.append(output_handling.CHECK_NAME)
    # Scoped the same way, and for the same reason: a repo that defines no agent
    # has nothing whose auditability could be judged, so the check is absent
    # rather than silent and AUDITABILITY reads as unexamined.
    if has_python and auditability.has_agent_surface(surfaces):
        ran.append(auditability.CHECK_NAME)
    return ran
