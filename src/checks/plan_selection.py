"""Turns a model's choice of surfaces into a selection no check can be silenced by.

Task 7.4 reversed this phase's original rule: the planner may now narrow a check
to some of its surfaces, so a finding can go unfound because the model did not
look. `docs/HISTORY.md` carries the reversal and why. This module is the
containment, and it is pure -- no model call, no I/O.

**Five rules, each closing a way the narrowing could lie.**

1. *A check the model does not name runs on everything.* Silence is not a
   narrowing, so a garbled, empty or non-JSON reply leaves the audit at full
   coverage -- the same failure direction the order-only planner had.
2. *An empty selection is refused, not honoured.* A check named with no surfaces
   would sit in `coverage.checks_run` declaring its whole risk class examined,
   having looked at nothing. That is the false claim this phase exists to
   prevent, arriving by a legitimate path instead of a malformed one.
3. *Surfaces the prompt never described always run.* `describe_surfaces` caps
   what the model is shown; under selection semantics that cap would otherwise
   subtract silently, excluding surfaces the model was never told existed.
4. *A check this app does not run cannot be narrowed*, and the two
   component-anchored checks are never narrowable at all. `supply_chain` and
   `known_advisory` read the mapping document, not the surface list: filtering
   their surfaces makes a component vanish from *both* sides of the ledger --
   no finding, and not counted as unreached either.
5. *Every refusal is recorded.* A narrowing that was rejected must be
   distinguishable from a narrowing never asked for, the way `model_run` tells
   `unavailable` from `disabled`.
"""

from artifacts.surface import Surface

# Checks whose subject is a surface, and which may therefore be narrowed to
# some of them. `supply_chain` and `known_advisory` are deliberately absent --
# see rule 4. `run_checks` asserts at import that these are checks it knows.
NARROWABLE_CHECKS = frozenset({
    "high_privilege_tool", "untrusted_input_reaches_model",
    "unsafe_query_construction", "agent_defined_without_callback_handler",
    "semantic_probe",
})

# Why a narrowing was refused. Closed, and recorded in `planner.json`.
UNKNOWN_CHECK = "unknown_check"
NOT_NARROWABLE = "not_narrowable"
UNKNOWN_SURFACE = "unknown_surface_id"
EMPTY_SELECTION = "empty_selection"
REFUSAL_REASONS = (UNKNOWN_CHECK, NOT_NARROWABLE, UNKNOWN_SURFACE, EMPTY_SELECTION)


def _refusal(check: str, surface_ids: list[str], reason: str) -> dict:
    """Record one narrowing that was asked for and not honoured."""
    return {"check": check, "surface_ids": sorted(surface_ids), "reason": reason}


def _named_ids(asked: object) -> list[str]:
    """The surface ids in one check's entry, dropping anything that is not a string."""
    return [name for name in asked if isinstance(name, str)] if isinstance(asked, list) else []


def _judge(check: str, asked: object, eligible: set[str],
           describable: set[str]) -> tuple[set[str] | None, dict | None]:
    """Decide one check's selection, or say why it was refused.

    Returns `(chosen, None)` when the narrowing stands and `(None, refusal)`
    when it does not. `chosen` is only ever a subset of what the model was
    actually shown -- rule 3 adds the rest back at the call site.
    """
    if check not in eligible:
        # Not planned on this app, so there is nothing to narrow. Refused before
        # the narrowable test, because a narrowing record for a check absent
        # from `checks_run` is a contradiction the coverage validator raises on
        # -- and an exception out of `build_findings` is not the full-coverage
        # fallback rule 1 promises.
        return None, _refusal(check, _named_ids(asked), UNKNOWN_CHECK)
    if check not in NARROWABLE_CHECKS:
        return None, _refusal(check, _named_ids(asked), NOT_NARROWABLE)
    named = set(_named_ids(asked))
    if not named:
        return None, _refusal(check, [], EMPTY_SELECTION)
    unknown = named - describable
    if unknown:
        return None, _refusal(check, sorted(unknown), UNKNOWN_SURFACE)
    return named, None


def resolve(selection: dict, eligible: list[str], described: list[Surface],
            all_surfaces: list[Surface]) -> tuple[dict[str, set[str]], list[dict]]:
    """Turn the model's asked-for selection into the surface ids each check will examine.

    A check absent from the result examines everything, which is what every
    check did before this task and what a silent model still gets.
    """
    describable = {surface.id for surface in described}
    # Rule 3: what the model never saw is never excluded.
    unseen = {surface.id for surface in all_surfaces} - describable
    chosen: dict[str, set[str]] = {}
    refused: list[dict] = []
    for check, asked in sorted(selection.items()):
        picked, refusal = _judge(check, asked, set(eligible), describable)
        if refusal is not None:
            refused.append(refusal)
            continue
        chosen[check] = picked | unseen
    return chosen, refused


def surfaces_for(check: str, chosen: dict[str, set[str]],
                 surfaces: list[Surface]) -> list[Surface]:
    """The surfaces one check examines: its selection, or all of them when unselected."""
    picked = chosen.get(check)
    if picked is None:
        return surfaces
    return [surface for surface in surfaces if surface.id in picked]


def narrowing_records(chosen: dict[str, set[str]], surfaces: list[Surface]) -> list[dict]:
    """What `findings.json` reports about each check that examined only some surfaces."""
    eligible = len(surfaces)
    return [{"check": check,
             "examined_surface_count": len(surfaces_for(check, chosen, surfaces)),
             "eligible_surface_count": eligible}
            for check in sorted(chosen)
            if len(surfaces_for(check, chosen, surfaces)) < eligible]
