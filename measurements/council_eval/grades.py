"""How far each vector a roster reached lands from R1, in CVSS severity bands.

A council vector's band is set beside the band of the R1 vector for the same
finding (`council_eval.vectors`), and each pair is counted by how many bands
apart they are: **exact** (the same band), **adjacent** (one apart) or **major**
(two or more). The bands are the specification's, in order from None to
Critical, as `cvss.score` names them.

Only a vector with a full R1 is graded: where R1 lacks a metric there is no R1
band to compare with, and such a vector is counted apart rather than graded.
Every number is the engine's, from the vectors beside it.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from cvss.score import SEVERITY_BANDS

from council_eval.reference import NO_FULL_REFERENCE
from council_eval.tables import table
from council_eval.vectors import VectorMeasure, reference_band

# Lowest first, so a difference of positions is a difference of bands.
BAND_ORDER = tuple(name for _, name in reversed(SEVERITY_BANDS))
EXACT = "exact"
ADJACENT = "adjacent"
MAJOR = "major"
GRADES = (EXACT, ADJACENT, MAJOR)
GRADE_COLUMNS = ("finding", "council band", "R1 band", "bands apart", "grade")


@dataclass(frozen=True)
class GradeMeasure:
    """One vector's band beside R1's, how many bands apart they are, and the grade that makes."""

    key: str
    band: str
    reference_band: str
    apart: int

    @property
    def grade(self) -> str:
        """Name the agreement: the same band, one apart, or two or more."""
        if self.apart == 0:
            return EXACT
        return ADJACENT if self.apart == 1 else MAJOR


def grade_measures(vectors: Iterable[VectorMeasure]) -> tuple[GradeMeasure, ...]:
    """Grade every vector that has a full R1 to compare with, in the order they were reached."""
    return tuple(grade_of(one) for one in vectors if reference_band(one) != NO_FULL_REFERENCE)


def grade_of(vector: VectorMeasure) -> GradeMeasure:
    """Set one vector's band beside R1's."""
    reference = reference_band(vector)
    return GradeMeasure(vector.key, vector.band, reference, bands_apart(vector.band, reference))


def bands_apart(band: str, other: str) -> int:
    """Count how many severity bands lie between two, refusing a name that is not a band."""
    if band not in BAND_ORDER or other not in BAND_ORDER:
        raise ValueError(f"{band!r} and {other!r} must both be one of {', '.join(BAND_ORDER)}")
    return abs(BAND_ORDER.index(band) - BAND_ORDER.index(other))


def grade_lines(vectors: tuple[VectorMeasure, ...]) -> list[str]:
    """Count one roster's vectors by grade, then lay out every graded one."""
    graded = grade_measures(vectors)
    counted = Counter(one.grade for one in graded)
    grades = ", ".join(f"{counted[grade]} {grade}" for grade in GRADES)
    ungraded = len(vectors) - len(graded)
    summary = (
        f"{counted_vectors(len(vectors))}; {len(graded)} with a full R1: {grades}; "
        f"{ungraded} without a full R1, not graded"
    )
    rows = [[one.key, one.band, one.reference_band, one.apart, one.grade] for one in graded]
    return [summary, *table(GRADE_COLUMNS, rows)]


def counted_vectors(count: int) -> str:
    """Count vectors, in the singular where there is one."""
    return f"{count} vector" if count == 1 else f"{count} vectors"
