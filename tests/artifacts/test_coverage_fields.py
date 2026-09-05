"""Every key `coverage` publishes, and every key its readers expect to find.

Nothing enumerated `coverage`'s key set before task 7.4, so the block could gain
a field that no reader knew about and lose one that three readers subscript --
the second crashes, the first is silent, and silence is the worse of the two.
This file names the set once and asserts it from both directions, in the shape
`tests/evaluation/test_artifact_field_cover.py` uses for the scorer.

**One key is deliberately absent, and that absence is the test.**
`artifacts/sarif.py` copies `coverage` **wholesale** into `findings.sarif.json`,
which is published as byte-identical every run. `checks_narrowed` is the one
field a model can move, so it sits at the *top level* of `findings.json`
instead. A future change that tidied it into `coverage` would push
model-determined bytes into an artifact documented as deterministic, and this
is where that would be caught.

Limit, the same one the sibling file records: `subscript_keys` matches a
constant key off a plain name, so `findings_document["coverage"]["advisory_data"]`
-- a chained subscript, which is how `scorer.py` and `emit_vex.py` read it --
is not seen. The three modules below all bind `coverage` to a name first.
"""

from artifacts.coverage import ADVISORY_SNAPSHOT, coverage
from ast_scan import parse, subscript_keys
from conftest import SRC_DIR

# Every key the block carries, in the order `coverage` assembles them. A reader
# is promised all ten, present-and-null rather than absent, so a missing key
# never has to be told apart from a null one.
COVERAGE_FIELDS = (
    "surfaces_considered",
    "checks_run",
    "risk_classes_checked",
    "unresolved_component_count",
    "advisory_data",
    "advisory_generator_name",
    "advisory_generator_version",
    "advisory_db_updated_at",
    "advisory_unreached_component_count",
    "advisory_unreached_components",
)

# The modules that bind the block to a name called `coverage` and read keys off
# it. Each would raise a bare `KeyError` mid-report on a key the block lost.
READERS = ("report.py", "report_gaps.py", "artifacts/vex.py")

# A pin, so the snapshot branch of every reader is reachable from one block.
PINNED = {"advisory_generator_name": "trivy", "advisory_generator_version": "0.58.1",
          "advisory_db_updated_at": "2026-08-30T12:00:00Z"}


def built() -> dict:
    """One coverage block with every optional part filled in, so no key is null-by-absence."""
    return coverage(3, ["high_privilege_tool"], ADVISORY_SNAPSHOT,
                    risk_classes_checked=["LLM06"], unresolved_component_count=1,
                    advisory_unreached_component_count=0,
                    advisory_unreached_components=[], **PINNED)


def test_the_block_holds_exactly_the_documented_keys_in_the_documented_order() -> None:
    """Both directions at once: a new key fails this, and so does a dropped one."""
    assert tuple(built()) == COVERAGE_FIELDS


def test_a_default_block_holds_the_same_keys_as_a_fully_pinned_one() -> None:
    """Present and null, never absent -- a reader reads one shape whatever the run did."""
    assert tuple(coverage(0, [])) == COVERAGE_FIELDS


def test_the_documented_keys_are_the_ten_the_schema_lists() -> None:
    """Guard: an emptied tuple would make the two comparisons above pass over nothing."""
    assert len(COVERAGE_FIELDS) == 10


def test_every_key_a_reader_subscripts_is_one_the_block_publishes() -> None:
    """The direction that catches a crash: an unlisted key reaches a reader unguarded."""
    for name in READERS:
        read = subscript_keys(parse(SRC_DIR / name), "coverage")
        assert read <= set(COVERAGE_FIELDS), f"{name}: {sorted(read - set(COVERAGE_FIELDS))}"


def test_the_scan_really_finds_reads_in_each_of_those_modules() -> None:
    """Guard: a scan that found nothing would make the subset above vacuously true."""
    for name in READERS:
        assert subscript_keys(parse(SRC_DIR / name), "coverage")


def test_the_narrowing_record_is_not_a_coverage_key() -> None:
    """`sarif.py` copies `coverage` wholesale, so a model-moved field may not live in it."""
    assert "checks_narrowed" not in built()
