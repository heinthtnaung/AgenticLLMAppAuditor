"""What one source published about one advisory, read and scored on its own.

Up to five sources score a CVE and they disagree on roughly two findings in
five, so each is read separately and none is preferred. A source whose vector
this calculator cannot read is kept as a source that was not scored, never
dropped and never scored zero: a v2 or v4.0 published vector is a real
occurrence, and an audit that fell over on one would report nothing at all.

The two records are separate types on purpose. A single record with an optional
score would let "nobody scored this" and "somebody scored this 0.0" be told
apart only by remembering to check, and those are different findings.
"""

from dataclasses import dataclass

from cvss.score import base_score
from cvss.vector import CvssVector, parse
from deps.trivy_runner import Advisory


@dataclass(frozen=True)
class SourceScore:
    """One source's published vector, quoted, and the base score derived from it.

    `vector` is the string as the source published it and is never edited;
    `parsed_vector` is that same reading in this project's own terms, kept so a
    finding can say which metrics its sources disagree on without re-parsing.
    """

    source: str
    vector: str
    parsed_vector: CvssVector
    base_score: float


@dataclass(frozen=True)
class UnreadableSource:
    """One source's published vector that this calculator refused, kept with the reason."""

    source: str
    vector: str
    refusal: str


ReadSource = SourceScore | UnreadableSource


def read_sources(advisory: Advisory) -> list[ReadSource]:
    """Read every source that published a vector for an advisory, in source-name order."""
    # Sorted here rather than trusted from the caller, so a finding built from a
    # hand-made advisory orders its sources the same way a scanned one does.
    return [read_source(source, text) for source, text in sorted(advisory.vectors.items())]


def read_source(source: str, published: str) -> ReadSource:
    """Score one source's published vector, or record why it could not be read."""
    try:
        parsed = parse(published)
    except ValueError as refusal:
        return UnreadableSource(source=source, vector=published, refusal=str(refusal))
    return SourceScore(
        source=source,
        vector=published,
        parsed_vector=parsed,
        base_score=base_score(parsed),
    )
