"""R1, the published reference: a metric's value where two organisations read it the same.

**Red Hat, corroborated by NVD or GHSA.** Measured over the 1,189 corpus
advisories, `julia` gives NVD's full vector on 112 of 112 and `bitnami` on 134 of
140, so agreement that counts either of them is mostly NVD counted twice; and
GHSA gives NVD's on 251 of 333, often plausibly because NVD republishes the
GitHub CNA's score. Red Hat is the source left that most plausibly scores for
itself, and even that is an assumption the data cannot test: it gives NVD's
full vector on 414 of 753.

**A metric with no agreement has no reference**, and is absent from the mapping
rather than present as a guess. A council answer there is neither right nor
wrong by R1: it is left out of the denominator and counted separately. That is
also why R1 cannot score a metric the sources dispute -- by construction, which
is the council's default workload.

A vector the calculator refuses is no reading of anything, so it corroborates
nothing here.
"""

from typing import Mapping

from cvss.metrics import METRIC_ORDER
from cvss.vector import parse

ANCHOR_SOURCE = "redhat"
CORROBORATING_SOURCES = ("nvd", "ghsa")
VECTOR_PREFIX = "CVSS:3.1/"
NO_FULL_REFERENCE = ""


def r1_reference(vectors: Mapping[str, str]) -> dict[str, str]:
    """Give each metric's R1 value, holding only the metrics that have one."""
    readable = readable_metrics(vectors)
    if ANCHOR_SOURCE not in readable:
        return {}
    anchor = readable[ANCHOR_SOURCE]
    others = [readable[source] for source in CORROBORATING_SOURCES if source in readable]
    agreed = [metric for metric in METRIC_ORDER if corroborated(metric, anchor, others)]
    return {metric: anchor[metric] for metric in agreed}


def corroborated(metric: str, anchor: Mapping[str, str], others: list[Mapping[str, str]]) -> bool:
    """Say whether any corroborating source reads one metric as the anchor does."""
    return any(other[metric] == anchor[metric] for other in others)


def readable_metrics(vectors: Mapping[str, str]) -> dict[str, Mapping[str, str]]:
    """Give each source's Base metrics, for the sources whose vector the calculator reads."""
    return {source: parse(text).metrics for source, text in vectors.items() if is_readable(text)}


def is_readable(vector: str) -> bool:
    """Say whether the calculator reads a published vector."""
    try:
        parse(vector)
    except ValueError:
        return False
    return True


def full_reference(vectors: Mapping[str, str]) -> str:
    """Give the R1 vector where every metric has a reference, and `NO_FULL_REFERENCE` otherwise."""
    reference = r1_reference(vectors)
    if len(reference) < len(METRIC_ORDER):
        return NO_FULL_REFERENCE
    pairs = "/".join(f"{metric}:{reference[metric]}" for metric in METRIC_ORDER)
    return f"{VECTOR_PREFIX}{pairs}"
