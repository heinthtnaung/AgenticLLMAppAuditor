"""The eight CVSS Base metrics: their order, their names in words, their legal values.

The vocabulary lives here so that the parser and the equations agree on it by
construction rather than by both remembering the same table -- and so does the
check that holds a metric and its value to it, which the council's answers and
rulings are held to as well.
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
    # ValueError and not the dict's own KeyError: every refusal its neighbours in
    # `cvss.vector` raise is a ValueError, and a caller wrapping vector work in
    # `except ValueError` would otherwise sail straight past this one.
    metric = METRICS_BY_ABBREVIATION.get(abbreviation)
    if metric is None:
        raise ValueError(
            f"{abbreviation!r} is not a CVSS Base metric; "
            f"the eight are {', '.join(METRIC_ORDER)}"
        )
    return metric.name


def refuse_illegal_pair(name: str, value: str) -> None:
    """Refuse a metric this calculator does not know, or a value that metric forbids."""
    metric = METRICS_BY_ABBREVIATION.get(name)
    if metric is None:
        raise ValueError(
            f"Unknown metric {name!r}: this calculator reads the eight CVSS Base metrics only"
        )
    if value not in metric.values:
        allowed = ", ".join(metric.values)
        raise ValueError(
            f"{value!r} is not a value of {metric.name} ({name}); allowed values are {allowed}"
        )
