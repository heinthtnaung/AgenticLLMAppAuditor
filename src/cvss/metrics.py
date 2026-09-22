"""The eight CVSS Base metrics: their order, their names in words, their legal values.

The vocabulary lives here so that the parser and the equations agree on it by
construction rather than by both remembering the same table.
"""

from dataclasses import dataclass

ATTACK_VECTOR = "AV"
ATTACK_COMPLEXITY = "AC"
PRIVILEGES_REQUIRED = "PR"
USER_INTERACTION = "UI"
SCOPE = "S"
CONFIDENTIALITY = "C"
INTEGRITY = "I"
AVAILABILITY = "A"

SCOPE_UNCHANGED = "U"
SCOPE_CHANGED = "C"

IMPACT_METRICS = (CONFIDENTIALITY, INTEGRITY, AVAILABILITY)


@dataclass(frozen=True)
class BaseMetric:
    """One Base metric: its abbreviation, its name in words, and the values it allows."""

    abbreviation: str
    name: str
    values: tuple[str, ...]


# Specification order. `CvssVector.__str__` rebuilds a vector in this order, so
# this tuple is what makes two spellings of one assessment compare equal.
BASE_METRICS: tuple[BaseMetric, ...] = (
    BaseMetric(ATTACK_VECTOR, "Attack Vector", ("N", "A", "L", "P")),
    BaseMetric(ATTACK_COMPLEXITY, "Attack Complexity", ("L", "H")),
    BaseMetric(PRIVILEGES_REQUIRED, "Privileges Required", ("N", "L", "H")),
    BaseMetric(USER_INTERACTION, "User Interaction", ("N", "R")),
    BaseMetric(SCOPE, "Scope", (SCOPE_UNCHANGED, SCOPE_CHANGED)),
    BaseMetric(CONFIDENTIALITY, "Confidentiality", ("H", "L", "N")),
    BaseMetric(INTEGRITY, "Integrity", ("H", "L", "N")),
    BaseMetric(AVAILABILITY, "Availability", ("H", "L", "N")),
)

METRIC_ORDER: tuple[str, ...] = tuple(metric.abbreviation for metric in BASE_METRICS)

METRICS_BY_ABBREVIATION: dict[str, BaseMetric] = {
    metric.abbreviation: metric for metric in BASE_METRICS
}


def metric_name(abbreviation: str) -> str:
    """Give a Base metric's name in words, so a refusal reads as English."""
    return METRICS_BY_ABBREVIATION[abbreviation].name
