"""Rules 4 and 5: which checks may be narrowed at all, and how a refusal is recorded.

The sibling of `test_plan_selection.py`, which owns the three rules about
surfaces. These two are about *checks*.

**Rule 4** keeps `undeclared_dependency` and `known_advisory` out of
`NARROWABLE_CHECKS`. Both read the mapping document rather than the surface
list, so filtering their surfaces makes a component vanish from *both* sides of
the coverage ledger at once -- no finding about it, and not counted as unreached
either. That is worse than either failure alone, because neither number moves
and a reader sees a consistent, wrong answer.

**Rule 5** says every refusal is recorded. A narrowing that was rejected has to
be distinguishable from one nobody asked for, the way `model_run` tells
`unavailable` from `disabled`. Without the record, a model asking to narrow
everything and being refused every time writes the same file as a model that
said nothing.

Everything here is pure: `resolve` is called directly, over the fixture the
sibling file describes.
"""

import pytest

from checks import plan_selection
from checks.auditability import CHECK_NAME as AUDITABILITY_CHECK
from checks.known_advisory import CHECK_NAME as ADVISORY_CHECK
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK
from plan_selection_fixtures import (
    CHOSEN_ID, ELIGIBLE, GHOST_ID, refusal_reasons, resolve)


# --- rule 4: the component-anchored checks are never narrowable -------------

@pytest.mark.parametrize("check", [SUPPLY_CHAIN_CHECK, ADVISORY_CHECK])
def test_a_component_anchored_check_is_refused_as_not_narrowable(check: str) -> None:
    """Both read the mapping, not the surface list, so filtering surfaces loses a component.

    It would vanish from both sides of the ledger at once: no finding about it,
    and not counted as unreached either.
    """
    chosen, refused = resolve({check: [CHOSEN_ID]})
    assert chosen == {}
    assert refusal_reasons(refused) == [plan_selection.NOT_NARROWABLE]


@pytest.mark.parametrize("check", [SUPPLY_CHAIN_CHECK, ADVISORY_CHECK])
def test_neither_component_anchored_check_is_in_the_narrowable_set(check: str) -> None:
    """Asserted against the constant as well, so the refusal above cannot be a coincidence."""
    assert check not in plan_selection.NARROWABLE_CHECKS


# --- rule 4, stated as a whole: which checks may be narrowed at all ----------

def test_the_narrowable_set_is_the_five_the_module_docstring_claims() -> None:
    """Guard: an emptied set would refuse everything and pass every test above it."""
    assert len(plan_selection.NARROWABLE_CHECKS) == 5


# --- an invented check name --------------------------------------------------

def test_a_check_name_the_auditor_does_not_have_is_refused() -> None:
    """An invented name must not reach `checks_narrowed`, which names checks that ran."""
    chosen, refused = resolve({"check_the_vibes": [CHOSEN_ID]})
    assert chosen == {}
    assert refusal_reasons(refused) == [plan_selection.UNKNOWN_CHECK]


def test_an_invented_name_is_told_apart_from_one_that_merely_cannot_be_narrowed() -> None:
    """Two different mistakes, so two different reasons: one is a typo, one is rule 4."""
    _chosen, invented = resolve({"check_the_vibes": [CHOSEN_ID]})
    _chosen, refused = resolve({SUPPLY_CHAIN_CHECK: [CHOSEN_ID]})
    assert refusal_reasons(invented) != refusal_reasons(refused)


# --- a narrowable check this app never planned -------------------------------

def test_a_narrowable_check_this_app_does_not_run_is_refused() -> None:
    """`build_prompt` lists only the eligible checks, so naming another is a mistake.

    Honoured, the narrowing reaches `findings.json` as a `checks_narrowed`
    record for a check absent from `checks_run` -- which `check_narrowings`
    refuses by raising, so the model's reply ends the audit instead of being
    contained. Rule 1 says a bad narrowing falls back to full coverage; a crash
    is not a fallback.
    """
    unplanned = "unsafe_query_construction"
    assert unplanned in plan_selection.NARROWABLE_CHECKS and unplanned not in ELIGIBLE
    chosen, refused = resolve({unplanned: [CHOSEN_ID]})
    assert chosen == {}
    assert refusal_reasons(refused) == [plan_selection.UNKNOWN_CHECK]


def test_the_edge_check_is_never_narrowed_because_no_app_plans_it() -> None:
    """`semantic_probe` runs outside the graph and is never in the eligible list.

    `run_checks._checks_that_examined_something` never names it, so under the
    rule above it can never be narrowed -- which is the only safe answer, since
    `build_findings` hands the probe `surfaces` rather than the narrowed list
    and a recorded narrowing would therefore be a count of a filter nobody
    applied.
    """
    chosen, refused = resolve({"semantic_probe": [CHOSEN_ID]})
    assert chosen == {}
    assert refusal_reasons(refused) == [plan_selection.UNKNOWN_CHECK]


# --- rule 5: every refusal is recorded --------------------------------------

def test_a_refusal_carries_the_check_the_ids_and_the_reason() -> None:
    """The three fields `planner.json` publishes, so a reader can act on the record."""
    _chosen, refused = resolve({TAINT_CHECK: [GHOST_ID]})
    assert refused == [{"check": TAINT_CHECK, "surface_ids": [GHOST_ID],
                        "reason": plan_selection.UNKNOWN_SURFACE}]


def test_the_ids_in_a_refusal_are_sorted() -> None:
    """The artifact is stable, so a set's iteration order must not reach the file."""
    _chosen, refused = resolve({TAINT_CHECK: ["z-ghost", "a-ghost"]})
    assert refused[0]["surface_ids"] == ["a-ghost", "z-ghost"]


def test_every_reason_the_guard_produces_is_in_the_published_set() -> None:
    """A reason outside `REFUSAL_REASONS` would reach `planner.json` unlookuppable."""
    _chosen, refused = resolve({TAINT_CHECK: [], SUPPLY_CHAIN_CHECK: [CHOSEN_ID],
                                "invented": [CHOSEN_ID], AUDITABILITY_CHECK: [GHOST_ID]})
    assert len(refused) == 4
    assert set(refusal_reasons(refused)) == set(plan_selection.REFUSAL_REASONS)


def test_one_good_narrowing_beside_three_bad_ones_survives() -> None:
    """A refusal contains itself: it must not cost the check that asked correctly."""
    chosen, refused = resolve({TAINT_CHECK: [CHOSEN_ID], SUPPLY_CHAIN_CHECK: [CHOSEN_ID],
                               "invented": [CHOSEN_ID], AUDITABILITY_CHECK: []})
    assert sorted(chosen) == [TAINT_CHECK]
    assert len(refused) == 3
