"""`checks_narrowed`: what a narrowed check may claim about itself, and what it may not.

Five invariants, and each one closes a way the record could be true of nothing:

1. `examined <= eligible <= surfaces_considered`, so the fraction is a fraction
   of what the audit actually walked.
2. No check named twice, because two records would be two different answers to
   one question.
3. The check has to be in `coverage.checks_run`: a check that examined some of
   its surfaces did look, and `docs/SCHEMAS.md` defines a name there as exactly
   that.
4. `examined == eligible` is **refused**, which is what makes `[]` a reliable
   test for "nothing was narrowed" -- every reader branches on exactly that.
5. Exactly three fields, so nothing undocumented reaches `findings.json`.

Written against `check_narrowings` directly rather than through a whole audit:
a validator is worth testing on the records a producer would have to be broken
to emit, and those are the ones no audit will hand it.
"""

import pytest

from artifacts.coverage import NARROWED_FIELDS, check_narrowings
from checks.auditability import CHECK_NAME as AUDITABILITY_CHECK
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK

# The checks that ran, and how many surfaces the audit considered in total.
CHECKS_RUN = [AUDITABILITY_CHECK, PERMISSION_CHECK, TAINT_CHECK]
CONSIDERED = 5


def narrowing(check: str = TAINT_CHECK, examined: int = 2,
              eligible: int = CONSIDERED) -> dict:
    """One narrowing record, valid unless a test changes a number in it."""
    return {"check": check, "examined_surface_count": examined,
            "eligible_surface_count": eligible}


def check(narrowed: list[dict]) -> list[dict]:
    """Validate a list of records against the fixed run above."""
    return check_narrowings(narrowed, CHECKS_RUN, CONSIDERED)


# --- the shape ---------------------------------------------------------------

def test_no_narrowings_is_an_empty_list() -> None:
    """The common case, and the one every reader branches on."""
    assert check([]) == []


def test_a_valid_record_passes_through_unchanged() -> None:
    """Guard: a validator that rewrote its input would make the refusals below untestable."""
    assert check([narrowing()]) == [narrowing()]


def test_the_published_fields_are_the_three_the_schema_lists() -> None:
    """Guard: an emptied tuple would make the field refusal below pass over nothing."""
    assert NARROWED_FIELDS == ("check", "examined_surface_count", "eligible_surface_count")


def test_a_record_with_a_fourth_field_is_refused() -> None:
    """An undocumented field would reach `findings.json` unvalidated and unread."""
    extra = narrowing() | {"surface_ids": ["agent.py:1:TOOL_CALL:Tool0"]}
    with pytest.raises(ValueError, match="must hold exactly"):
        check([extra])


def test_a_record_missing_a_field_is_refused() -> None:
    """A count with no denominator beside it is the one thing this field must never be."""
    missing = {"check": TAINT_CHECK, "examined_surface_count": 2}
    with pytest.raises(ValueError, match="must hold exactly"):
        check([missing])


# --- invariant 1: examined <= eligible <= considered -------------------------

def test_examining_more_surfaces_than_were_eligible_is_refused() -> None:
    """Not a fraction of what was there, so not a narrowing of anything."""
    with pytest.raises(ValueError, match="not a fraction"):
        check([narrowing(examined=6, eligible=5)])


def test_more_eligible_surfaces_than_the_audit_considered_is_refused() -> None:
    """The denominator cannot exceed the surfaces the whole run walked."""
    with pytest.raises(ValueError, match="not a fraction"):
        check([narrowing(examined=2, eligible=CONSIDERED + 1)])


def test_a_negative_examined_count_is_refused() -> None:
    """Zero is the floor: a check cannot have examined fewer surfaces than none."""
    with pytest.raises(ValueError, match="not a fraction"):
        check([narrowing(examined=-1)])


def test_examining_none_of_the_eligible_surfaces_is_accepted() -> None:
    """Zero is a real answer, and the guard against it is `plan_selection`'s, not this one.

    Refusing it here would move rule 2 into the wrong module and hide a
    producer bug behind a crash in the validator.
    """
    assert check([narrowing(examined=0)]) == [narrowing(examined=0)]


# --- invariant 4: examined == eligible is not a narrowing --------------------

def test_a_check_that_examined_every_eligible_surface_is_refused() -> None:
    """This is what makes `[]` mean "nothing was narrowed" rather than "possibly nothing"."""
    with pytest.raises(ValueError, match="that is not a narrowing"):
        check([narrowing(examined=CONSIDERED, eligible=CONSIDERED)])


def test_the_equal_case_is_refused_below_the_considered_count_too() -> None:
    """Guard: the refusal is `examined == eligible`, not `examined == considered`."""
    with pytest.raises(ValueError, match="that is not a narrowing"):
        check([narrowing(examined=3, eligible=3)])


# --- invariant 2: no check named twice ---------------------------------------

def test_two_records_naming_the_same_check_are_refused() -> None:
    """Two answers to one question, and a reader has no rule for choosing between them."""
    with pytest.raises(ValueError, match="the same check"):
        check([narrowing(examined=1), narrowing(examined=2)])


def test_two_records_naming_different_checks_are_accepted() -> None:
    """Guard: the duplicate refusal must not refuse the ordinary two-check case."""
    assert len(check([narrowing(TAINT_CHECK), narrowing(PERMISSION_CHECK)])) == 2


# --- invariant 3: the check has to have run ----------------------------------

def test_a_narrowed_check_that_is_not_in_checks_run_is_refused() -> None:
    """A check that narrowed its surfaces looked; absent from `checks_run` it did not.

    `docs/SCHEMAS.md` reads that absence as "could not look at all" and the
    scorer as `no_check_for_risk_class`, so the two claims contradict.
    """
    with pytest.raises(ValueError, match="not in checks_run"):
        check([narrowing("unsafe_query_construction")])


def test_an_invented_check_name_is_refused_for_the_same_reason() -> None:
    """A name the auditor does not have cannot have examined anything."""
    with pytest.raises(ValueError, match="not in checks_run"):
        check([narrowing("check_the_vibes")])


# --- the order the records are published in ----------------------------------

def test_the_records_come_back_sorted_by_check() -> None:
    """The artifact is stable, so the producer's order must not reach the file."""
    records = check([narrowing(TAINT_CHECK), narrowing(AUDITABILITY_CHECK)])
    assert [entry["check"] for entry in records] == [AUDITABILITY_CHECK, TAINT_CHECK]
