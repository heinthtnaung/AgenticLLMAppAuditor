"""What `council.redaction` catches, what it lets past, and what widening it costs.

Run it: `python measurements/redaction_gaps.py`. It needs Trivy and the database
snapshot, and it touches no network and no model.

Every figure in `council.redaction`'s docstring is printed here. The two that
decide the design are the last two: a pattern is worth adding when it costs
nothing on real advisories, and worth refusing when it eats them.
"""

import re
import sys
from itertools import chain
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advisories import advisory_texts  # noqa: E402
from council.redaction import (  # noqa: E402
    CVE_IDENTIFIER,
    GHSA_IDENTIFIER,
    IDENTIFIER_MARKER,
    VECTOR_MARKER,
    redact,
)

# The patterns as they stood before a bare vector was redacted, so the cost of
# adding one can be counted rather than argued.
REDACTIONS_BEFORE: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bCVSS:\d\.\d(?:/[A-Za-z]+:[A-Za-z])+"), VECTOR_MARKER),
    (CVE_IDENTIFIER, IDENTIFIER_MARKER),
    (GHSA_IDENTIFIER, IDENTIFIER_MARKER),
)

VECTOR_SHAPES = {
    "a vector carrying its CVSS:d.d prefix": re.compile(r"\bCVSS:\d\.\d(?:/[A-Za-z]+:[A-Za-z])+"),
    "a bare v3 Base vector, all eight": re.compile(
        r"\bAV:[NALP]/AC:[LH]/PR:[NLH]/UI:[NR]/S:[UC]/C:[NLH]/I:[NLH]/A:[NLH]\b"
    ),
    "a bare v2 Base vector, all six": re.compile(
        r"\bAV:[NAL]/AC:[HML]/Au:[MSN]/C:[NPC]/I:[NPC]/A:[NPC]\b"
    ),
    "any run of two or more metric pairs": re.compile(
        r"\b(?:[A-Za-z]{1,2}:[A-Za-z]/)+[A-Za-z]{1,2}:[A-Za-z]\b"
    ),
}

NAMESPACES = (
    "PYSEC", "RUSTSEC", "OSV", "SNYK", "DSA", "DLA", "USN", "RHSA", "ELSA",
    "ALAS", "GLSA", "NSWG", "TEMP", "MAL",
)
NAMESPACE_IDENTIFIER = re.compile(
    rf"\b(?:{'|'.join(NAMESPACES)})-[0-9A-Za-z]+(?:-[0-9A-Za-z]+)*\b"
)

PROSE_SCORE = re.compile(
    r"\(\s*\d{1,2}\.\d\s*[,/]?\s*(?:critical|high|medium|low|none)\s*\)", re.IGNORECASE
)
ANY_DECIMAL = re.compile(r"\b\d+\.\d+\b")


def redact_as_before(text: str) -> str:
    """Redact the way the module did before a bare vector counted as a published score."""
    for pattern, marker in REDACTIONS_BEFORE:
        text = pattern.sub(marker, text)
    return text


def matching(texts: dict[str, str], pattern: re.Pattern[str]) -> dict[str, list[str]]:
    """Give the advisories a pattern fires on, and what it found in each."""
    return {
        advisory_id: pattern.findall(text)
        for advisory_id, text in texts.items()
        if pattern.search(text)
    }


def report_vector_shapes(texts: dict[str, str], redacted: dict[str, str]) -> None:
    """Say which vector shapes occur in the raw text, and which survive redaction."""
    print("\nvector shapes, in the advisory as the database carries it:")
    for described, pattern in VECTOR_SHAPES.items():
        hits = matching(texts, pattern)
        print(f"  {len(hits):5} {described}")
    surviving = matching(redacted, VECTOR_SHAPES["any run of two or more metric pairs"])
    print(f"  {len(surviving):5} still vector-shaped after redaction {sorted(surviving)}")


def report_namespaces(redacted: dict[str, str]) -> None:
    """Say which identifier namespaces reach a member after CVE and GHSA are taken out."""
    hits = matching(redacted, NAMESPACE_IDENTIFIER)
    found = sorted(set(chain.from_iterable(hits.values())))
    print(f"\nidentifiers in other namespaces surviving redaction: {len(hits)} advisories {found}")
    carrying_own_id = [
        advisory_id for advisory_id, text in redacted.items() if advisory_id.lower() in text.lower()
    ]
    print(f"advisories containing their own id: {len(carrying_own_id)}")


def report_prose_scores(texts: dict[str, str]) -> None:
    """Say how many advisories publish a score in words, and what catching them would cost."""
    hits = matching(texts, PROSE_SCORE)
    print(f"\nprose scores: {len(hits)} advisories {sorted(hits)}")
    print(f"advisories carrying any x.y number: {len(matching(texts, ANY_DECIMAL))}")
    print("  -- a general pattern over those eats fixed versions, which is why the gap stays open")


def report_widening_cost(texts: dict[str, str]) -> None:
    """Say how many advisories the bare-vector pattern changed, which is the cost of adding it."""
    changed = [
        advisory_id
        for advisory_id, text in texts.items()
        if redact_as_before(text) != redact(text).text
    ]
    print(f"\nadvisories the bare-vector pattern redacts differently: {len(changed)} {changed}")


def main() -> None:
    """Print every figure `council.redaction`'s docstring cites."""
    texts = advisory_texts()
    redacted = {
        advisory_id: redact(text).text for advisory_id, text in texts.items() if text.strip()
    }
    print(f"{len(texts)} distinct advisories")
    report_vector_shapes(texts, redacted)
    report_namespaces(redacted)
    report_prose_scores(texts)
    report_widening_cost(texts)


if __name__ == "__main__":
    main()
