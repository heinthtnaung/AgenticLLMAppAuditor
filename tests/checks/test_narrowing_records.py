"""What `findings.json` is told about a narrowed check, and what it is not told.

`plan_selection.narrowing_records` is the producer; `artifacts/coverage.py`'s
`check_narrowings` is the validator that refuses what it produces. Two modules
for one record, so this file owns the producer and
`tests/artifacts/test_coverage_narrowings.py` owns the validator -- and
`tests/checks/test_narrowed_run.py` joins them over a real audit.

The one rule that is easy to lose: a check whose selection came out as the whole
list produces **no record at all**. `check_narrowings` refuses `examined ==
eligible`, so a producer that emitted one would fail the audit rather than the
test -- and, more to the point, `[]` would stop being a reliable test for
"nothing was narrowed", which is what every reader branches on.
"""

from artifacts.surface import DATA_SOURCE, TOOL_CALL, Surface
from checks.auditability import CHECK_NAME as AUDITABILITY_CHECK
from checks.plan_selection import narrowing_records
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK
from parsing.languages import PYTHON

# Four surfaces, so a selection of one, two or three is a real fraction and the
# denominator in each record can be checked against a number written here.
SURFACES = [Surface(TOOL_CALL, f"Tool{index}", "agent.py", index + 1, PYTHON, "tool",
                    "langchain.tools")
            for index in range(3)] + [
    Surface(DATA_SOURCE, "yaml.load", "utils.py", 75, PYTHON, "yaml read", "yaml")]
ELIGIBLE_COUNT = 4

FIRST, SECOND = SURFACES[0].id, SURFACES[1].id
EVERY_ID = {surface.id for surface in SURFACES}


def test_nothing_narrowed_produces_no_records() -> None:
    """The empty selection: `[]` is what a reader branches on, so it has to be exact."""
    assert narrowing_records({}, SURFACES) == []


def test_a_narrowed_check_reports_what_it_examined_and_what_it_could_have() -> None:
    """Counts and their denominator, never a rate -- the division stays the reader's."""
    assert narrowing_records({TAINT_CHECK: {FIRST}}, SURFACES) == [
        {"check": TAINT_CHECK, "examined_surface_count": 1,
         "eligible_surface_count": ELIGIBLE_COUNT}]


def test_the_examined_count_is_the_surfaces_the_check_really_gets() -> None:
    """Guard: the count is derived from the same filter `act` applies, not from the set size."""
    records = narrowing_records({TAINT_CHECK: {FIRST, SECOND}}, SURFACES)
    assert records[0]["examined_surface_count"] == 2


def test_a_selection_of_every_surface_produces_no_record() -> None:
    """`examined == eligible` is not a narrowing, and the validator refuses one that claims it."""
    assert narrowing_records({TAINT_CHECK: EVERY_ID}, SURFACES) == []


def test_a_selection_naming_ids_this_app_does_not_have_counts_only_what_matched() -> None:
    """The guard refuses these upstream; here the count must not be the set's length."""
    records = narrowing_records({TAINT_CHECK: {FIRST, "nowhere.py:1:TOOL_CALL:Ghost"}}, SURFACES)
    assert records[0]["examined_surface_count"] == 1


def test_two_narrowed_checks_are_sorted_by_check_name() -> None:
    """The artifact is stable, so a dict's insertion order must not reach the file."""
    records = narrowing_records(
        {TAINT_CHECK: {FIRST}, AUDITABILITY_CHECK: {SECOND}}, SURFACES)
    assert [entry["check"] for entry in records] == [AUDITABILITY_CHECK, TAINT_CHECK]


def test_only_the_narrowed_check_of_two_gets_a_record() -> None:
    """One narrowed and one at full coverage: the record is per check, not per selection."""
    records = narrowing_records(
        {TAINT_CHECK: {FIRST}, PERMISSION_CHECK: EVERY_ID}, SURFACES)
    assert [entry["check"] for entry in records] == [TAINT_CHECK]


def test_every_record_holds_exactly_the_three_published_fields() -> None:
    """A fourth field would reach `findings.json` undocumented and unvalidated."""
    records = narrowing_records({TAINT_CHECK: {FIRST}}, SURFACES)
    assert sorted(records[0]) == ["check", "eligible_surface_count", "examined_surface_count"]


def test_an_app_with_no_surfaces_narrows_nothing() -> None:
    """Zero eligible means zero examined, and `0 < 0` is false: no record, no division."""
    assert narrowing_records({TAINT_CHECK: {FIRST}}, []) == []
