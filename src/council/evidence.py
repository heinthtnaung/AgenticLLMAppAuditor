"""The quotation check: does a member's evidence appear in the text it was given?

This is why the council is auditable rather than persuasive. A rationale can
argue anything; a quotation can be verified, and `docs/COUNCIL.md` makes it
application code's job to verify it -- the same check for every member, because
a hosted member earns no extra trust by costing money.

**`advisory_text` is the text the member actually saw, not the raw advisory.**
The panel rule keeps the CVE id and the published scores away from a member, so
the text it reads is redacted before it is sent. Checking a quotation against
the unredacted advisory would fail every quotation that spans a redaction, and
fail it in the worst direction: the metric would come out unresolved, which
reads as the advisory having said nothing rather than as a caller having passed
the wrong string.

**What "appears in" means here.** Exact substring, after folding two things that
carry no meaning:

- **whitespace**, every run of it to one space. Where an advisory wraps its
  lines is a layout accident of the feed it arrived in, not part of what it
  says, and a model that reflows it is not paraphrasing.
- **typographic quote characters**, to their ASCII forms. A model that types
  `don't` where the advisory has `don’t` has quoted it.

**A quotation of our own redaction marker is not a quotation.** The markers are
in the text the member read, so `[identifier withheld]` verifies as a substring
of it -- and supports nothing, because it is what this system put there, not
what the advisory said. A verified quotation that supports nothing defeats the
one property the council rests on. So a quotation must carry a word of the
advisory's own **outside** any marker. Not "must contain no marker": a quotation
spanning one is a legitimate quotation of what the member actually read, and
refusing it would throw away real evidence.

Nothing else. In particular **case is not folded** and no words are dropped,
stemmed, reordered or matched approximately, so the check cannot be satisfied by
a paraphrase: every normalisation above preserves the exact sequence of words and
their characters, and a paraphrase by definition does not. Loosening it further
would mean accepting text the advisory does not contain, which is the one thing
this function exists to refuse.
"""

import re

from council.redaction import REDACTIONS

# Quote characters a model substitutes without changing what was said.
TYPOGRAPHIC_EQUIVALENTS = {
    "‘": "'",
    "’": "'",
    "‚": "'",
    "“": '"',
    "”": '"',
    "„": '"',
    "′": "'",
    "″": '"',
}

WHITESPACE_RUN = re.compile(r"\s+")

# The panel rule: a member never sees the CVE id, so text still carrying one is
# not text any member read. This encodes that rule and not anyone's redaction --
# an id still matchable here means redaction failed and a member is about to be
# shown one, which is the run stopping rather than this check misfiring.
CVE_IDENTIFIER = re.compile(r"CVE-\d{4}-\d{4,}", re.IGNORECASE)

# A quotation has to contain a word. Punctuation alone appears in almost any
# advisory and would verify every time while supporting nothing.
WORD_CHARACTER = re.compile(r"\w")

# What this system substituted for what it took out, read off the redactions
# themselves rather than restated: a marker added there is discounted here
# without anyone remembering to, and the two cannot drift apart.
REDACTION_MARKERS: tuple[str, ...] = tuple(dict.fromkeys(m for _, m in REDACTIONS))


def is_quotation_from(quotation: str, advisory_text: str) -> bool:
    """Say whether a member's evidence is really present in the advisory it read."""
    refuse_empty_advisory(advisory_text)
    refuse_unredacted(advisory_text)
    if not quotes_the_advisory(quotation):
        return False
    return normalise(quotation) in normalise(advisory_text)


def quotes_the_advisory(quotation: str) -> bool:
    """Say whether a quotation carries a word of the advisory's own, outside any marker."""
    return bool(WORD_CHARACTER.search(without_markers(quotation)))


def without_markers(text: str) -> str:
    """Take out what this system substituted, leaving only what the advisory said."""
    for marker in REDACTION_MARKERS:
        text = text.replace(marker, " ")
    return text


def normalise(text: str) -> str:
    """Fold the layout and the typography, and nothing that changes a word."""
    folded = "".join(TYPOGRAPHIC_EQUIVALENTS.get(character, character) for character in text)
    return WHITESPACE_RUN.sub(" ", folded).strip()


def refuse_unredacted(advisory_text: str) -> None:
    """Refuse advisory text still carrying a CVE id, which is not what a member read."""
    found = CVE_IDENTIFIER.search(advisory_text)
    if not found:
        return
    raise ValueError(
        f"This advisory text still contains {found.group()}, so it is not the text a "
        "member was shown: the panel rule keeps the CVE id away from a member. Check a "
        "quotation against the redacted text the member read, not the raw advisory."
    )


def refuse_empty_advisory(advisory_text: str) -> None:
    """Refuse to check against text that is not there, rather than failing every member."""
    # No quotation can verify against nothing, so returning False would mark
    # every member unverified and read as n models having failed. An advisory
    # with no text is a broken finding, and that is a different report.
    if not isinstance(advisory_text, str):
        raise TypeError(f"An advisory must be text, not {type(advisory_text).__name__}")
    if not advisory_text.strip():
        raise ValueError("There is no advisory text to check a quotation against")
