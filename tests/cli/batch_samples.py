"""Four findings for the batch tests: two left open, one settled, and one the council passes over.

Every reply depends on the finding and the call alone, never on when the call is
made, so a run asked in any order hears the same answers. What each council
leaves open is its advisory's row in `LEFT_OPEN`: S declined by both members is
unresolved, and AC answered L by one and H by the other is contested.
"""

import json

from cli.council_run import assess_one, build_roster, escalation_member, passed_over, to_assess
from cli.progress import NO_PROGRESS
from cli_samples import LEGAL, LODASH, LOW_CONFIDENTIALITY, TOTAL_LOSS, advisory_like
from findings.finding import build_finding

BIG = "big:27b"
COUNCIL = build_roster(("small", "other"))
ESCALATION = escalation_member(BIG)
DISPUTED = {"ghsa": TOTAL_LOSS, "nvd": LOW_CONFIDENTIALITY}
AGREED = {"ghsa": TOTAL_LOSS, "nvd": TOTAL_LOSS}
# How much of each advisory a member quotes: its opening words, so the quotation verifies.
QUOTED_LENGTH = 24

OPEN_ON_S = "A remote attacker can inject commands through a template option."
SETTLED = "A crafted archive lets a local user overwrite any file on the host."
OPEN_ON_AC_AND_S = "An unauthenticated request can read the memory of the server."
NOT_ASKED = "A long header makes the parser allocate without bound."
LEFT_OPEN = {OPEN_ON_S: ("S",), SETTLED: (), OPEN_ON_AC_AND_S: ("AC", "S"), NOT_ASKED: ()}
# The escalation model settles S on the first advisory, and declines it on the third.
BIG_DECLINES = {OPEN_ON_AC_AND_S: ("S",)}
# The value a member other than the first gives a contested metric.
DISSENT = {"AC": "H"}

ADVISORIES = (
    advisory_like("CVE-OPEN-S", details=OPEN_ON_S, vectors=DISPUTED),
    advisory_like("CVE-SETTLED", details=SETTLED, vectors=DISPUTED),
    advisory_like("CVE-NOT-ASKED", details=NOT_ASKED, vectors=AGREED),
    advisory_like("CVE-OPEN-AC-S", details=OPEN_ON_AC_AND_S, vectors=DISPUTED),
)
FINDINGS = tuple(build_finding(LODASH, one) for one in ADVISORIES)


def answering(calls: list):
    """Give a client that notes each call and answers it from the finding's row alone."""

    def said(member, prompt) -> str:
        """Note the call, then answer it as this member always answers this metric here."""
        text = prompt.advisory_shown
        calls.append((member.name, text, prompt.metric, prompt.version))
        return json.dumps(reply_of(member.name, text, prompt.metric))

    return {"ollama": said}


def reply_of(member: str, text: str, metric: str) -> dict:
    """Give one member's reply to one metric of one advisory, whatever was asked before it."""
    if declines(member, text, metric):
        return {"value": "NO_EVIDENCE", "evidence": ""}
    dissents = member == "other" and metric in LEFT_OPEN[text]
    value = DISSENT[metric] if dissents else LEGAL[metric]
    return {"value": value, "evidence": text[:QUOTED_LENGTH], "confidence": "high"}


def declines(member: str, text: str, metric: str) -> bool:
    """Say whether a member finds nothing to quote: an open S, or what `BIG_DECLINES` names."""
    if member == BIG:
        return metric in BIG_DECLINES.get(text, ())
    return metric == "S" and metric in LEFT_OPEN[text]


def one_finding_at_a_time(
    findings, roster, clients, progress=NO_PROGRESS, every_finding=False, escalation=None
):
    """Assess as the audit did before the batch: each council, then its escalation, in turn."""
    # `assess_one` is also the step the evaluation harness replays one finding at a time.
    assessed = [
        assess_one(one, roster, clients, progress, escalation=escalation)
        for one in to_assess(findings, every_finding)
    ]
    return (*assessed, *passed_over(findings, every_finding))
