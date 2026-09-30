"""Reading a Trivy report: the advisories it found, indexed by what they were raised against.

Trivy's own field names stop here, so no later step has to know which tool
produced a finding. Nothing in this file runs anything; `deps.trivy_runner` does
that and hands the parsed document over.
"""

from collections import defaultdict
from dataclasses import dataclass
from itertools import chain
from types import MappingProxyType
from typing import Any, Mapping

from deps.scanner import ScannerFailed

# Trivy's own field names, spelled out once here and nowhere else in the project.
RESULTS = "Results"
VULNERABILITIES = "Vulnerabilities"
ADVISORY_ID = "VulnerabilityID"
PACKAGE_IDENTIFIER = "PkgIdentifier"
PACKAGE_URL = "PURL"
FIXED_VERSION = "FixedVersion"
SUMMARY = "Title"
DETAILS = "Description"
SCORES_BY_SOURCE = "CVSS"
V3_VECTOR = "V3Vector"
PRIMARY_URL = "PrimaryURL"

UNIDENTIFIED_ADVISORY = "<unidentified>"
# The advisory's link is put on the page as one, so a scheme a browser would run
# rather than open is refused here instead of being escaped into a live href.
WEB_SCHEMES = ("https://", "http://")


@dataclass(frozen=True)
class Advisory:
    """One advisory against one component version, with every source's vector kept apart.

    `fixed_version` is None when no fix is published, and is otherwise quoted as
    the advisory writes it, which may name several release branches at once.
    `url` is the advisory's own page as Trivy names it, and None when it names none.
    """

    advisory_id: str
    purl: str
    fixed_version: str | None
    summary: str
    details: str
    vectors: Mapping[str, str]
    url: str | None = None

    def __post_init__(self) -> None:
        """Lock the vectors, so no later step can quietly reconcile the sources."""
        object.__setattr__(self, "vectors", MappingProxyType(dict(self.vectors)))


def read_advisories(report: Any) -> dict[str, tuple[Advisory, ...]]:
    """Read a parsed Trivy report into advisories, indexed by the purl they were raised against."""
    records = advisory_records(report)
    return index_by_purl([read_advisory(record) for record in records])


def advisory_records(report: Any) -> list:
    """Flatten the per-target results into one list of advisory records."""
    return list(chain.from_iterable(target_records(result) for result in report_results(report)))


def report_results(report: Any) -> list[Mapping[str, Any]]:
    """Give a report's per-target results, refusing a document of another shape."""
    if not isinstance(report, Mapping):
        raise ScannerFailed("A Trivy report must be a JSON object")
    # A report with nothing to say omits the key entirely rather than emptying it.
    results = report.get(RESULTS) or []
    if not isinstance(results, list):
        raise ScannerFailed(f"A Trivy report's {RESULTS!r} must be a list of targets")
    return [target_result(result) for result in results]


def target_result(result: Any) -> Mapping[str, Any]:
    """Give one target's result, refusing an entry that is not an object."""
    if not isinstance(result, Mapping):
        raise ScannerFailed(f"Each entry of a Trivy report's {RESULTS!r} must be an object")
    return result


def target_records(result: Mapping[str, Any]) -> list:
    """Give one target's advisory records, which Trivy omits when it found none."""
    return result.get(VULNERABILITIES) or []


def read_advisory(record: Any) -> Advisory:
    """Translate one Trivy record into an advisory of this project's own vocabulary."""
    if not isinstance(record, Mapping):
        raise ScannerFailed("A Trivy advisory record must be a JSON object")
    return Advisory(
        advisory_id=read_advisory_id(record),
        purl=read_purl(record),
        fixed_version=record.get(FIXED_VERSION) or None,
        summary=record.get(SUMMARY) or "",
        details=record.get(DETAILS) or "",
        vectors=read_vectors(record),
        url=read_url(record),
    )


def read_advisory_id(record: Mapping[str, Any]) -> str:
    """Give the advisory's published id, refusing a record that names none."""
    advisory_id = record.get(ADVISORY_ID)
    if not advisory_id:
        raise ScannerFailed("A Trivy advisory record carries no advisory id")
    return advisory_id


def read_purl(record: Mapping[str, Any]) -> str:
    """Give the versioned purl an advisory was raised against, which is the join key."""
    identifier = record.get(PACKAGE_IDENTIFIER)
    purl = identifier.get(PACKAGE_URL) if isinstance(identifier, Mapping) else None
    if not purl:
        named = record.get(ADVISORY_ID) or UNIDENTIFIED_ADVISORY
        raise ScannerFailed(f"Advisory {named!r} carries no package URL to join it on")
    return purl


def read_url(record: Mapping[str, Any]) -> str | None:
    """Give the advisory's own web page, None when Trivy names none, refusing anything else."""
    # Absent and empty are both no link, and are kept as None: an empty string
    # rendered as a link is a link to nothing that looks like a link to something.
    url = record.get(PRIMARY_URL)
    if url is None or url == "":
        return None
    if not isinstance(url, str) or not url.startswith(WEB_SCHEMES):
        named = record.get(ADVISORY_ID) or UNIDENTIFIED_ADVISORY
        said = f"Advisory {named!r} carries a {PRIMARY_URL} that is not a web link: {url!r}"
        raise ScannerFailed(said)
    return url


def read_vectors(record: Mapping[str, Any]) -> dict[str, str]:
    """Keep every source's CVSS v3 vector, attributed by source name and never merged."""
    # Up to five sources score one CVE and they disagree on two findings in five;
    # NVD is absent from roughly one in five. Collapsing them here, or preferring
    # one of them, would throw away the disagreement the council exists to weigh.
    published = record.get(SCORES_BY_SOURCE) or {}
    if not isinstance(published, Mapping):
        raise ScannerFailed(f"A Trivy record's {SCORES_BY_SOURCE!r} must be an object")
    vectors = {
        source: entry[V3_VECTOR]
        for source, entry in published.items()
        if isinstance(entry, Mapping) and entry.get(V3_VECTOR)
    }
    return dict(sorted(vectors.items()))


def index_by_purl(advisories: list[Advisory]) -> dict[str, tuple[Advisory, ...]]:
    """Group advisories by purl, in a fixed order so two scans produce identical output."""
    grouped: dict[str, list[Advisory]] = defaultdict(list)
    for advisory in advisories:
        grouped[advisory.purl].append(advisory)
    return {purl: tuple(sorted(grouped[purl], key=advisory_order)) for purl in sorted(grouped)}


def advisory_order(advisory: Advisory) -> str:
    """Order the advisories against one component by their published id."""
    return advisory.advisory_id
