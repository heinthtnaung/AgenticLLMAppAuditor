"""Taking out of an advisory the things a member must not see.

`docs/COUNCIL.md` fixes what a member reads: the advisory text only, not the
published scores and **not the CVE id**. A model that recognises
`CVE-2021-44228` recites it from training, and then what the council measures is
memorisation. Trivy's advisory `details` routinely carries both the id and, in
some feeds, a published vector, so the rule has to be applied to the text rather
than asked for in the prompt: a sentence in the prompt cannot unsee an id.

**What comes out** is CVE and GHSA identifiers and CVSS vector strings, each
replaced by a marker rather than deleted, so a sentence still reads as a
sentence and a member can still quote it.

**What does not** is a score written as prose -- "this issue carries a base
score of 9.8" names no vector. That gap was measured rather than left open:
across both corpora, the 18 vulnscout advisories and 135 from the out-of-date
PyPI manifest, **no advisory carries one**, while 137 of those 153 contain some
`x.y` number -- and every one sampled is a version. A looser pattern would eat
the fixed version, which is the most useful thing an advisory says, on nine
advisories in ten to catch nothing. So the gap stays open knowingly; a corpus
of vendor advisory pages rather than database records would be worth
re-measuring.

The redacted text is what the member saw, so it is also the text its quotation
must be checked against. `council.evidence` is given this, never the original.
"""

import re
from dataclasses import dataclass

# Non-capturing throughout: `findall` gives whole matches, which is what the
# record of a redaction needs.
#
# The identifiers are unbounded in length on purpose. A CVE sequence number is
# four digits or more with no upper limit, and a pattern that guesses an upper
# one lets past it exactly the ids the panel rule exists to stop.
# `council.evidence` enforces the same rule from the other side with its own
# pattern, and the two agreeing on what an identifier looks like is the design.
CVE_IDENTIFIER = re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.IGNORECASE)
GHSA_IDENTIFIER = re.compile(r"\bGHSA(?:-[0-9a-z]{4,})+\b", re.IGNORECASE)
PUBLISHED_VECTOR = re.compile(r"\bCVSS:\d\.\d(?:/[A-Za-z]+:[A-Za-z])+")

IDENTIFIER_MARKER = "[identifier withheld]"
VECTOR_MARKER = "[published score withheld]"

REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (PUBLISHED_VECTOR, VECTOR_MARKER),
    (CVE_IDENTIFIER, IDENTIFIER_MARKER),
    (GHSA_IDENTIFIER, IDENTIFIER_MARKER),
)


@dataclass(frozen=True)
class RedactedAdvisory:
    """An advisory as a member will see it, and what was taken out of it."""

    text: str
    removed: tuple[str, ...]


def redact(advisory_text: str) -> RedactedAdvisory:
    """Take the identifiers and published vectors out of an advisory, keeping a record."""
    refuse_empty(advisory_text)
    removed: list[str] = []
    text = advisory_text
    for pattern, marker in REDACTIONS:
        text, found = replace_all(text, pattern, marker)
        removed.extend(found)
    return RedactedAdvisory(text=text, removed=tuple(removed))


def replace_all(text: str, pattern: re.Pattern[str], marker: str) -> tuple[str, list[str]]:
    """Replace every match with a marker, and say what was replaced."""
    return pattern.sub(marker, text), pattern.findall(text)


def refuse_empty(advisory_text: str) -> None:
    """Refuse an advisory with no text, rather than prompting a member with nothing."""
    if not isinstance(advisory_text, str):
        raise TypeError(f"An advisory must be text, not {type(advisory_text).__name__}")
    if not advisory_text.strip():
        raise ValueError("There is no advisory text to assess")
