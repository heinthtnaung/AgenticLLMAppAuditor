"""What the council did, on the page, led by the metrics a reader has to decide.

Eight metrics by n members for every assessed finding is more page than anyone
reads, and most of it is agreement. So the page shows the metrics the chairman
could **not** settle -- contested and unresolved -- with every member's answer,
its evidence and whether that evidence checked out, and counts the settled rest
on one line. The audit record carries all of it; this chooses.

Contested is the case the whole project exists for. Two model families reading
one advisory and reaching different values, each with a quotation that verifies,
is not something a count can express -- and a human exercising the override the
design gives them needs to see who said what, on what evidence.
"""

from report.council_record import CouncilAssessment, MemberSaid, MetricRuling, Outcome, SaidKind
from report.text_layout import INDENT, SOURCE_SEPARATOR, section

EVIDENCE_WIDTH = 60
VERIFIED = "quoted"
UNVERIFIED = "not in the advisory"


def council_block(report) -> str:
    """Say what the council did for each advisory, keeping its two outcomes apart."""
    if not report.council:
        return ""
    entries = [
        line
        for advisory_id in sorted(report.council)
        for line in advisory_lines(advisory_id, report.council[advisory_id])
    ]
    return section(f"COUNCIL ({len(report.council)})", entries)


def advisory_lines(advisory_id: str, outcome) -> list[str]:
    """Give one advisory's heading, then the metrics the chairman could not settle."""
    unsettled = [one for one in outcome.rulings if one.outcome is not Outcome.SETTLED]
    settled = len(outcome.rulings) - len(unsettled)
    return [
        f"{INDENT}{advisory_id}  {headline(outcome)}{settled_note(settled)}",
        *[line for ruling in unsettled for line in ruling_lines(ruling)],
    ]


def headline(outcome) -> str:
    """Say whether the council handed over a vector, or what stopped it."""
    if isinstance(outcome, CouncilAssessment):
        return f"settled{SOURCE_SEPARATOR}{outcome.vector}"
    still_open = ", ".join(outcome.unresolved_metrics + outcome.contested_metrics)
    return f"no vector{SOURCE_SEPARATOR}could not settle {still_open}"


def settled_note(settled: int) -> str:
    """Count the metrics nobody needs to read, rather than printing them."""
    return f"{SOURCE_SEPARATOR}{settled} metrics settled" if settled else ""


def ruling_lines(ruling: MetricRuling) -> list[str]:
    """Give one unsettled metric and every member behind it."""
    fell_back = f" (fell back to {ruling.fallback_source})" if ruling.fallback_source else ""
    return [
        f"{INDENT}{INDENT}{ruling.metric}  {ruling.outcome.value}{fell_back}",
        *[f"{INDENT}{INDENT}{INDENT}{said_line(one)}" for one in ruling.said],
    ]


def said_line(said: MemberSaid) -> str:
    """Give one member's answer, its evidence, and whether that evidence checked out."""
    who = f"{said.member.name} ({said.member.family})"
    if said.kind is not SaidKind.ANSWERED:
        return f"{who}  {said.kind.value}{trailing(said)}"
    checked = VERIFIED if said.verified else UNVERIFIED
    return f"{who}  {said.value}  {said.confidence}  {checked}  {quoted(said.evidence)}"


def trailing(said: MemberSaid) -> str:
    """Say what a member that did not answer left behind, if anything."""
    if said.kind is SaidKind.GUESSED:
        return f" {said.value} with nothing quoted"
    return f": {said.reason}" if said.reason else ""


def quoted(evidence: str) -> str:
    """Quote a member's evidence, shortened to keep one member on one line."""
    folded = " ".join(evidence.split())
    if len(folded) <= EVIDENCE_WIDTH:
        return f"{folded!r}"
    return f"{folded[:EVIDENCE_WIDTH]!r}..."
