"""Putting the council to the findings that need one, when the operator named members.

**Scoped to the findings whose published sources do not settle them.** A measured
two-member run over 18 findings made 288 calls (`measurements/council_runs/`),
and 13 of those findings carried sources that already agreed -- 208 of the calls
spent adjudicating what nothing disputed. Scoped, the same audit made 80.
The council exists to reconcile sources, so a finding with nothing to reconcile
is not its work. `--council-all-findings` asks about every one of them, because
a council that only reads contested findings can never discover that agreeing
sources are **both** wrong, and `docs/COUNCIL.md` says no source is the
reference the others are measured against. That loss is real and an operator
may refuse it.

**A finding nobody scored is asked about, not skipped.** Its sources do not agree
either -- there are none -- and it is the case where a council vector is the only
severity the finding will ever carry.

**Nor is one carrying a source that could not be read.** Agreement among the
sources that were read says nothing about the one that was refused, so "no
published source disagrees" would be a claim the same record contradicts.

**Every skip is recorded with its reason.** A finding the council was not asked
about, one it assessed and could not settle, and a run where nobody was named to
ask are three different facts, and a scoped run that recorded nothing for the
findings it passed over would report the first as the third.

**No fallback source is chosen here, because choosing one is forbidden.**
`docs/SCORING_MODEL.md` leaves open which published source wins, and the
chairman's unresolved branch falls back to a published vector -- so a caller has
to say which. This one says *none*: every metric is given a
`NoFallbackPublished`, because picking `nvd` or `ghsa` to fill a gap would be
exactly the precedence the design refuses to set, arriving through the back door
of an error path.

**Every council is asked before any escalation**, so a server that cannot hold the
escalation model beside the members needs to load it once per run; the saving is
unmeasured. No prompt or ruling reads the order, so the same replies give the same
record, byte for byte. But the order changes which model is warm, and a model can
answer differently warm and cold (`measurements/council_eval/compose.py`).

What a run comes to in the record is `cli.council_outcome`; what it may escalate,
and to which model, is `council.escalation`.
"""

from cli.council_detail import rulings_of
from cli.council_outcome import outcome_of
from cli.progress import NO_PROGRESS, CouncilProgress, orders_asked
from council.escalation import escalate, refuse_unfit_escalation
from council.prompt import build_prompt
from council.providers import ollama_member
from council.roster import Member, Roster, members_to_ask
from council.ruling import NoFallbackPublished
from council.run import CouncilRun
from council.runner import PROVIDER_CLIENTS, assess
from cvss.metrics import METRIC_ORDER
from findings.finding import Finding
from report.council_record import CouncilNotAsked, CouncilOutcome

# Every audit asks each metric in both orders (`council.order_check`); only the
# evaluation harness, which records and replays passes in one order, turns it off.
ORDER_CHECK = True

SOURCES_AGREE = "no published source disagrees, so there is nothing to reconcile"
NO_TEXT_TO_READ = "the advisory carries no text for a member to read"

NO_FALLBACK = NoFallbackPublished(
    reason="no published source may be preferred, so none was offered as a fallback"
)
FALLBACKS = {metric: NO_FALLBACK for metric in METRIC_ORDER}


def build_roster(models: tuple[str, ...]) -> Roster:
    """Turn the models an operator named into a roster of members on the settings' server."""
    return Roster(tuple(ollama_member(model) for model in models))


def escalation_member(model: str | None) -> Member | None:
    """Describe the escalation model as a member on the settings' server, or None where unnamed."""
    if model is None:
        return None
    return ollama_member(model)


def assessments(
    findings: tuple[Finding, ...], roster: Roster,
    clients=PROVIDER_CLIENTS, progress=NO_PROGRESS,
    every_finding: bool = False, order_check: bool = ORDER_CHECK,
    escalation: Member | None = None,
) -> tuple[CouncilOutcome, ...]:
    """Put the council to the findings that need one, and record why the rest were passed over."""
    # Refused before any call, rather than once the first advisory's council has run.
    refuse_unfit_escalation(escalation, tuple(one.name for one in roster.members), clients)
    # Every council before any escalation, so the escalation calls come last and together.
    asking = to_assess(findings, every_finding)
    councils = [(one, council_on(one, roster, clients, progress, order_check)) for one in asking]
    assessed = [
        escalated_at(position, one, council, escalation, clients, progress)
        for position, (one, council) in enumerate(councils, start=1)
    ]
    return (*assessed, *passed_over(findings, every_finding))


def to_assess(findings: tuple[Finding, ...], every_finding: bool) -> tuple[Finding, ...]:
    """Give the findings this run will actually put to the council."""
    return tuple(one for one in findings if not skipped_because(one, every_finding))


def passed_over(findings: tuple[Finding, ...], every_finding: bool) -> tuple[CouncilNotAsked, ...]:
    """Record every finding the council was not put to, each with the reason it was not."""
    skipped = [(one, skipped_because(one, every_finding)) for one in findings]
    return tuple(
        CouncilNotAsked(one.advisory.advisory_id, because) for one, because in skipped if because
    )


def skipped_because(finding: Finding, every_finding: bool) -> str:
    """Say why a finding is not put to the council, or nothing at all where it is."""
    if not advisory_text(finding):
        return NO_TEXT_TO_READ
    # Nobody published a vector, so there is no agreement to rely on and the
    # council is the only severity this finding will ever carry.
    if every_finding or not finding.is_scored:
        return ""
    # A source that could not be read is an opinion nobody checked, which is not
    # agreement: its vector may disagree with every one that was read.
    if finding.unreadable or finding.disputed_metrics():
        return ""
    return SOURCES_AGREE


def assess_one(
    finding: Finding, roster: Roster, clients,
    progress=NO_PROGRESS, order_check: bool = ORDER_CHECK,
    escalation: Member | None = None,
) -> CouncilOutcome:
    """Put one advisory to the council and escalate what it left open, handing on any vector."""
    council = council_on(finding, roster, clients, progress, order_check)
    return escalated_outcome(finding, council, escalation, clients, progress)


def council_on(
    finding: Finding, roster: Roster, clients, progress, order_check: bool
) -> CouncilRun:
    """Put one advisory to every member of the council, escalating nothing yet."""
    progress.starting(finding.advisory.advisory_id)
    return assess(advisory_text(finding), roster, FALLBACKS, clients, progress.asking, order_check)


def escalated_at(
    position: int, finding: Finding, council: CouncilRun,
    escalation: Member | None, clients, progress,
) -> CouncilOutcome:
    """Go back to the advisory at this place in the run and escalate what its council left open."""
    progress.returning_to(position, finding.advisory.advisory_id)
    return escalated_outcome(finding, council, escalation, clients, progress)


def escalated_outcome(
    finding: Finding, council: CouncilRun, escalation: Member | None, clients, progress
) -> CouncilOutcome:
    """Escalate what one advisory's council left open, and record what the run came to."""
    text = advisory_text(finding)
    run = escalate(council, text, escalation, clients, progress.escalating)
    # The text the members actually read, which is what their quotations were
    # checked against and so what the record has to re-check them against.
    rulings = rulings_of(run, build_prompt(METRIC_ORDER[0], text).advisory_shown)
    return outcome_of(finding, run, rulings)


def watching(
    findings: tuple[Finding, ...], roster: Roster, out,
    every_finding: bool = False, order_check: bool = ORDER_CHECK,
) -> CouncilProgress:
    """Count the calls this roster will make over the findings it will be asked about."""
    # Only the findings this run will ask about and only the members it will ask:
    # a total that counts calls nobody makes is a progress bar that never fills.
    asking = to_assess(findings, every_finding)
    orders = orders_asked(order_check)
    return CouncilProgress(len(asking), len(members_to_ask(roster)), out, orders)


def advisory_text(finding: Finding) -> str:
    """Give the text a member reads, which is the advisory's own description."""
    return finding.advisory.details.strip()
