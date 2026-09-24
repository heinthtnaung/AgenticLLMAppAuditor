"""One CVSS Base vector: parsed, validated, canonical, and immutable.

Both `CVSS:3.1` and `CVSS:3.0` are accepted. Their Base metrics and Base
equations are identical -- v3.1 only clarified the rounding wording -- so
refusing v3.0 would discard real advisory data for no difference in meaning.
The declared version is kept on the parsed object all the same, because a
published v3.0 *score* may differ from ours in the last decimal.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from cvss.metrics import METRIC_ORDER, metric_name, refuse_illegal_pair

VERSION_PREFIX = "CVSS"
FIELD_SEPARATOR = "/"
PAIR_SEPARATOR = ":"
PAIR_PART_COUNT = 2

SUPPORTED_VERSIONS = ("3.1", "3.0")

# Refused by name rather than as "unknown": different metrics, different formula.
REFUSED_VERSIONS = {
    "2.0": "CVSS v2 uses different metrics and a different formula",
    "4.0": "CVSS v4.0 uses different metrics and a different formula",
}

# A v2 vector carries no version prefix at all, so the Authentication metric --
# which exists in no other version -- is what identifies it.
V2_AUTHENTICATION = "Au"


@dataclass(frozen=True)
class CvssVector:
    """One CVSS Base vector: the version it declares and its eight metric values."""

    version: str
    metrics: Mapping[str, str]

    def __post_init__(self) -> None:
        """Lock the metric values, not just the fields holding them."""
        # `frozen` stops the field being reassigned but would leave a plain dict
        # writable. The council hands one vector to several members at once, and a
        # vector one member could edit would make their disagreement meaningless.
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))

    def value(self, abbreviation: str) -> str:
        """Give one metric's value, by its specification abbreviation."""
        if abbreviation not in self.metrics:
            raise ValueError(f"{abbreviation!r} is not a CVSS Base metric of this vector")
        return self.metrics[abbreviation]

    def with_metric(self, abbreviation: str, value: str) -> "CvssVector":
        """Derive a new vector with one metric changed, leaving this one untouched."""
        refuse_illegal_pair(abbreviation, value)
        changed = dict(self.metrics)
        changed[abbreviation] = value
        return CvssVector(version=self.version, metrics=changed)

    def __str__(self) -> str:
        """Rebuild the vector in specification order, so two spellings compare equal."""
        prefix = f"{VERSION_PREFIX}{PAIR_SEPARATOR}{self.version}"
        pairs = [f"{name}{PAIR_SEPARATOR}{self.metrics[name]}" for name in METRIC_ORDER]
        return FIELD_SEPARATOR.join([prefix, *pairs])


def parse(text: str) -> CvssVector:
    """Parse a CVSS v3.1 or v3.0 Base vector, refusing anything it cannot read exactly."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("A CVSS vector must be a non-empty string")
    fields = text.strip().split(FIELD_SEPARATOR)
    version = read_version(fields[0], text)
    metrics = read_metrics(fields[1:])
    refuse_missing_metrics(metrics)
    return CvssVector(version=version, metrics=metrics)


def differing_metrics(left: CvssVector, right: CvssVector) -> tuple[str, ...]:
    """Name the Base metrics two vectors disagree on, in specification order."""
    # The declared version is not a metric and is not compared; two vectors that
    # differ only in their prefix describe the same assessment.
    return tuple(name for name in METRIC_ORDER if left.value(name) != right.value(name))


def read_version(field: str, vector_text: str) -> str:
    """Read the CVSS:x.y prefix, refusing a version these equations do not compute."""
    name, _, version = field.partition(PAIR_SEPARATOR)
    if name != VERSION_PREFIX:
        raise ValueError(missing_prefix_message(vector_text))
    if version in REFUSED_VERSIONS:
        raise ValueError(f"CVSS v{version} is not supported: {REFUSED_VERSIONS[version]}")
    if version not in SUPPORTED_VERSIONS:
        readable = " or ".join(SUPPORTED_VERSIONS)
        raise ValueError(f"Unknown CVSS version {version!r}; this calculator reads {readable}")
    return version


def read_metrics(fields: list[str]) -> dict[str, str]:
    """Read the name:value pairs after the prefix, refusing the first fault found."""
    metrics: dict[str, str] = {}
    for field in fields:
        name, value = split_pair(field)
        refuse_illegal_pair(name, value)
        if name in metrics:
            raise ValueError(
                f"{metric_name(name)} ({name}) is given twice; a vector states each metric once"
            )
        metrics[name] = value
    return metrics


def split_pair(field: str) -> tuple[str, str]:
    """Split one name:value pair, refusing anything that is not exactly that shape."""
    parts = field.split(PAIR_SEPARATOR)
    if len(parts) != PAIR_PART_COUNT or not all(parts):
        raise ValueError(
            f"Malformed metric {field!r}: a CVSS vector is made of 'name:value' pairs"
        )
    return parts[0], parts[1]


def refuse_missing_metrics(metrics: Mapping[str, str]) -> None:
    """Refuse a partial vector: never default a metric nobody assessed."""
    missing = [name for name in METRIC_ORDER if name not in metrics]
    if not missing:
        return
    named = ", ".join(f"{metric_name(name)} ({name})" for name in missing)
    raise ValueError(f"A CVSS Base vector needs all eight metrics; missing: {named}")


def missing_prefix_message(vector_text: str) -> str:
    """Say what is wrong with a vector carrying no CVSS:x.y prefix."""
    if looks_like_version_2(vector_text):
        return (
            "This is a CVSS v2 vector: it carries an Authentication (Au) metric. "
            f"{REFUSED_VERSIONS['2.0']}"
        )
    supported = " or ".join(f"'{VERSION_PREFIX}{PAIR_SEPARATOR}{v}'" for v in SUPPORTED_VERSIONS)
    return f"A CVSS vector must start with {supported}"


def looks_like_version_2(vector_text: str) -> bool:
    """Spot a v2 vector, which has no version prefix but does have Authentication."""
    prefix = f"{V2_AUTHENTICATION}{PAIR_SEPARATOR}"
    return any(field.startswith(prefix) for field in vector_text.split(FIELD_SEPARATOR))
