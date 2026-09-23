"""The sentences both council renderings say, in one place so the two cannot drift.

The terminal and the web page describe one record, and two renderings that word
the same fact differently is a defect this project has found more than once. The
wording lives here; the spacing, the indenting and the markup stay with each
rendering, because those are the part that genuinely differs between a browser
and a terminal.

**Verified is not the same claim as quoted.** A member that offered a quotation
and a member whose quotation the advisory actually contains are different
findings, and the evidence rule turns entirely on the difference, so the sentence
says which rather than saying that a quotation was given.

Nothing here is formatted. Each function gives a phrase or a list of phrases, and
the caller joins them with whatever its medium separates things by.
"""

from report.council_record import MemberIdentity, MemberSaid, MetricRuling, SaidKind

SINGLE_ASSESSOR = "single assessor, nothing cross-checked"
NOT_ASKED = "not asked"
VERIFIED = "quotation found in the advisory"
UNVERIFIED = "quotation not found in the advisory"


def who(member: MemberIdentity) -> str:
    """Name a member, and its family only when that is not the name a second time."""
    if member.family == member.name:
        return member.name
    return f"{member.name} ({member.family})"


def checked(verified: bool) -> str:
    """Say whether a member's quotation was found in the advisory, which `quoted` does not."""
    return VERIFIED if verified else UNVERIFIED


def unanswered(said: MemberSaid) -> str:
    """Say what a member that did not answer left behind, if it left anything."""
    if said.kind is SaidKind.GUESSED:
        return f"guessed {said.value} with nothing quoted"
    if said.reason:
        return f"{said.kind.value}: {said.reason}"
    return said.kind.value


def chairman_said(ruling: MetricRuling) -> list[str]:
    """Give what the chairman decided and why -- the basis is the answer to who won."""
    said = [
        f"chairman: {ruling.value}" if ruling.value else "",
        ruling.basis,
        f"{ruling.confidence} confidence" if ruling.confidence else "",
        f"fell back to {ruling.fallback_source}" if ruling.fallback_source else "",
    ]
    return [one for one in said if one]


def counted(count: int, noun: str) -> str:
    """Give a count with its noun, singular when there is one of them."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"
