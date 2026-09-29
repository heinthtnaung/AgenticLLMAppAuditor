"""Guards on grading vectors against R1: bands apart, as exact, adjacent or major."""

import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest

import eval_samples  # noqa: F401  (puts the evaluation package on the path)
from council_eval.commands import main
from council_eval.grades import (
    ADJACENT,
    BAND_ORDER,
    EXACT,
    MAJOR,
    GradeMeasure,
    bands_apart,
    grade_lines,
    grade_measures,
)
from council_eval.reference import NO_FULL_REFERENCE
from council_eval.vectors import VectorMeasure

RUNS = Path(__file__).resolve().parents[3] / "measurements" / "council_eval_runs"
PILOT = RUNS / "pilot-vulnscout"
HIGH_VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N"  # 7.5 High
LOW_VECTOR = "CVSS:3.1/AV:N/AC:H/PR:H/UI:R/S:U/C:L/I:N/A:N"  # 2.0 Low


def vector(key: str, band: str, reference: str) -> VectorMeasure:
    """Give one reached vector in this band, with this R1 vector beside it."""
    return VectorMeasure(key, "", 0.0, band, 8, (), reference, {})


def test_the_bands_run_in_the_specification_s_order_from_none_to_critical():
    assert BAND_ORDER == ("None", "Low", "Medium", "High", "Critical")


@pytest.mark.parametrize(
    ("band", "other", "apart", "grade"),
    [("High", "High", 0, EXACT), ("Medium", "High", 1, ADJACENT), ("Low", "High", 2, MAJOR),
     ("None", "Critical", 4, MAJOR)],
)
def test_bands_apart_are_counted_in_either_direction_and_graded(band, other, apart, grade):
    assert bands_apart(band, other) == bands_apart(other, band) == apart
    assert GradeMeasure("CVE-1", band, other, apart).grade == grade


def test_a_name_that_is_not_a_band_is_refused():
    with pytest.raises(ValueError, match="must both be one of"):
        bands_apart("Severe", "High")


def test_only_a_vector_with_a_full_r1_is_graded_and_the_rest_are_counted_apart():
    vectors = (vector("CVE-1", "High", HIGH_VECTOR), vector("CVE-2", "High", NO_FULL_REFERENCE),
               vector("CVE-3", "High", LOW_VECTOR))
    assert [(one.key, one.grade) for one in grade_measures(vectors)] == [
        ("CVE-1", EXACT), ("CVE-3", MAJOR),
    ]
    assert grade_lines(vectors)[0] == (
        "3 vectors; 2 with a full R1: 1 exact, 0 adjacent, 1 major; 1 without a full R1, not graded"
    )


def graded(*argv: str) -> str:
    """Run the grades step and give what it printed."""
    printed = io.StringIO()
    with redirect_stdout(printed):
        assert main(["grades", "--dataset", str(PILOT / "vulnscout.dataset.json"), *argv]) == 0
    return printed.getvalue()


def test_the_pilot_s_pair_grades_as_its_four_vectors_read_against_r1():
    passes = (
        PILOT / "qwen2.5-7b-instruct.run1.replies.jsonl",
        PILOT / "llama3.2-latest.run2.replies.jsonl",
    )
    printed = graded("--replies", *map(str, passes))
    section = printed.split("ROSTER qwen2.5:7b-instruct + llama3.2:latest  (18 items)\n")[1]
    assert section.splitlines()[0] == (
        "4 vectors; 4 with a full R1: 2 exact, 2 adjacent, 0 major; 0 without a full R1, not graded"
    )


@pytest.mark.parametrize(
    "argv", [(), ("--replies", "a", "--forward", "b", "--reversed", "c"), ("--forward", "b")],
    ids=["nothing", "both kinds", "half a pair"],
)
def test_passes_of_both_kinds_or_half_a_pair_are_refused(argv):
    with pytest.raises(ValueError, match="give --replies, or --forward with --reversed"):
        main(["grades", "--dataset", str(PILOT / "vulnscout.dataset.json"), *argv])


def test_one_vector_is_counted_in_the_singular():
    assert grade_lines((vector("CVE-1", "High", HIGH_VECTOR),))[0].startswith("1 vector; 1 with")
