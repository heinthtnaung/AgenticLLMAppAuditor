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

**A vector counts with or without its `CVSS:3.1/` prefix.** The eight metrics
are the same published score either way, and the bare form is the sharper leak:
a member asked for Attack Vector is handed `AV:N` in the text it is meant to
reason from. The bare pattern has to start at a named CVSS metric key rather
than at any `word:letter`, which is what keeps it off a URL, a ratio and an
`RSA-2048`; measured over the corpus below it fires on one advisory and that
advisory really does carry a vector.

**What does not come out.** Three gaps, all measured over the same corpus:

1. **A score written as prose**, and the gap stays open deliberately. One
   advisory of the 1,187 carries one -- `GHSA-pw6j-qg29-8w7f` -- and it is the
   advisory that carries the vector. This is what a member reads there:

       Proposed CVSS 3.1:
       `[published score withheld]` (5.9, medium); attack complexity is
       High because exploitation depends on the application using differing
       per-request options on a shared client and on handle scheduling.

   **Two published scores are in that sentence and only one of them is
   catchable.** `(5.9, medium)` could be had by a pattern keyed on the severity
   word beside the number: it would fire once in 1,187 and eat nothing, where a
   general `x.y` pattern would eat the fixed version on 878 of them. But
   `attack complexity is High` is the published value of a Base metric, written
   in words, three words later -- and it is the metric a member asked about
   Attack Complexity is being asked to decide. No pattern reaches it that does
   not also eat the advisory's reasoning, which is the thing the member is there
   to read.

   So catching the closable half would leave this file claiming the published
   scores are withheld while the AC value stands in the one advisory that
   demonstrates the problem. **A guarantee that is wrong in the only case we can
   show is worse than a gap that is named**, and the reason to write the
   sentence out here rather than a rate is that a reader can check it.

2. **Identifier namespaces other than CVE and GHSA** -- PYSEC, RUSTSEC, OSV,
   SNYK, DSA, USN, RHSA and the rest. Measured: **SNYK once in 1,187**, inside a
   reference URL, and **none of the others at all**. Several of the prefixes are
   live words in advisory prose -- `DSA` appears twice in its cryptographic
   sense -- so a namespace list would be maintenance and false positives for one
   occurrence. The gap stays open knowingly and is worth re-measuring against a
   database that indexes those namespaces; this one indexes CVE, GHSA and,
   between them, six ids in three other namespaces.

3. **An id an advisory writes about itself** is not a case that arises here:
   **no advisory of the 1,187 contains its own id**. Every identifier found in
   the text is a cross-reference to another advisory.

**The corpus.** 1,187 distinct advisories from seven offline Trivy scans of this
machine's database snapshot: 254 PyPI, 163 npm, 74 Go, 29 Rust, 608 Debian 11,
109 Alpine 3.14, and the 18 of the repository under test. `measurements/` re-runs
every scan in it, and it holds the advisory above, which the 18 alone could not:
none of them carries a vector.

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

# One metric of a vector, as loose in the key as CVSS is: `Au` is v2's, `AT` and
# `VC` are v4.0's, and `MAV` is an environmental override.
METRIC_PAIR = r"[A-Za-z]+:[A-Za-z]"

# The metrics a vector opens with, across v2, v3.1 and v4.0. A bare vector has
# to start at one of them, and that is the whole of what keeps this pattern off
# ordinary text: anchored on any `word:letter` it would also match a `host:p/`
# in a URL or a `16:9/4:3` ratio. The single-letter metrics -- `S`, `C`, `I`,
# `A` -- are deliberately not openings. A run starting at one of those is the
# tail of a vector whose head this pattern already matched, or it is a fragment
# that is not a published score, and one letter is not enough to tell the two
# from a coincidence.
VECTOR_OPENING = "AV|AC|Au|AT|PR|UI|VC|VI|VA|SC|SI|SA"

PUBLISHED_VECTOR = re.compile(rf"\bCVSS:\d\.\d(?:/{METRIC_PAIR})+")
BARE_VECTOR = re.compile(rf"\b(?:{VECTOR_OPENING}):[A-Za-z](?:/{METRIC_PAIR})+")

IDENTIFIER_MARKER = "[identifier withheld]"
VECTOR_MARKER = "[published score withheld]"

# The prefixed vector goes first: it takes the `CVSS:3.1/` with it, which the
# bare pattern on its own would leave standing in front of a marker.
REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (PUBLISHED_VECTOR, VECTOR_MARKER),
    (BARE_VECTOR, VECTOR_MARKER),
    (CVE_IDENTIFIER, IDENTIFIER_MARKER),
    (GHSA_IDENTIFIER, IDENTIFIER_MARKER),
)


@dataclass(frozen=True)
class RedactedAdvisory:
    """An advisory as a member will see it, and every string taken out of it.

    `removed` is a log of the substitutions, not a set of them: it runs in the
    order of `REDACTIONS` rather than the order the strings stood in the
    advisory, and an id taken out three times is in it three times. So its
    length counts redactions and not distinct secrets, and a reader after
    "which things were withheld" wants it deduplicated.
    """

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
