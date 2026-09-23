"""Putting the council to each finding, when the operator named members to ask.

**No fallback source is chosen here, because choosing one is forbidden.**
`docs/SCORING_MODEL.md` leaves open which published source wins, and the
chairman's unresolved branch falls back to a published vector -- so a caller has
to say which. This one says *none*: every metric is given a
`NoFallbackPublished`, because picking `nvd` or `ghsa` to fill a gap would be
exactly the precedence the design refuses to set, arriving through the back door
of an error path.

The consequence is deliberate and worth stating. A council that leaves any metric
unresolved produces no vector, so the finding keeps its per-source scores side by
side with no winner. The vector is discarded; **the fact that a council ran is
not**, and neither is what it could not settle -- that is the escalation
policy's input, and throwing it away told the report no council had run at all.
"""

from cvss.metrics import METRIC_ORDER
from council.chairman import agreed_vector
from council.roster import Member, Roster, members_to_ask
from council.prompt import build_prompt
from council.runner import PROVIDER_CLIENTS, assess
from council.ruling import ContestedMetric, NoFallbackPublished, UnresolvedMetric
from findings.finding import Finding
from cli.council_detail import rulings_of
from cli.progress import NO_PROGRESS, CouncilProgress
from report.council_record import CouncilAssessment, CouncilOutcome, CouncilWithoutVector

OLLAMA_PROVIDER = "ollama"
FAMILY_SEPARATOR = ":"
VECTOR_VERSION = "3.1"

NO_FALLBACK = NoFallbackPublished(
    reason="no published source may be preferred, so none was offered as a fallback"
)
FALLBACKS = {metric: NO_FALLBACK for metric in METRIC_ORDER}


def build_roster(models: tuple[str, ...]) -> Roster:
    """Turn the models an operator named into a roster of local members."""
    return Roster(tuple(local_member(model) for model in models))


def local_member(model: str) -> Member:
    """Describe one model running on this machine's Ollama as a council member."""
    # The family is guessed from the tag, which is what a roster file would carry
    # properly. It is only read to judge how much a roster's agreement is worth,
    # never by the chairman, so a wrong guess costs a reader and not a number.
    return Member(
        name=model,
        provider=OLLAMA_PROVIDER,
        model=model,
        family=model.split(FAMILY_SEPARATOR)[0],
        runs_local=True,
    )


def assessments(
    findings: tuple[Finding, ...], roster: Roster, clients=PROVIDER_CLIENTS, progress=NO_PROGRESS
) -> tuple[CouncilOutcome, ...]:
    """Put the council to every finding that carries text to read, and keep what came back."""
    return tuple(
        assess_one(finding, roster, clients, progress)
        for finding in findings
        if advisory_text(finding)
    )


def assess_one(finding: Finding, roster: Roster, clients, progress=NO_PROGRESS) -> CouncilOutcome:
    """Put one advisory to the council, handing on a vector only where it reached one."""
    progress.starting(finding.advisory.advisory_id)
    text = advisory_text(finding)
    run = assess(text, roster, FALLBACKS, clients, progress.asking)
    # The text the members actually read, which is what their quotations were
    # checked against and so what the record has to re-check them against.
    rulings = rulings_of(run, build_prompt(METRIC_ORDER[0], text).advisory_shown)
    unresolved = metrics_of(run, UnresolvedMetric)
    contested = metrics_of(run, ContestedMetric)
    if unresolved or contested:
        # With no fallback offered, an unsettled metric has no value and a partial
        # vector is not something the engine may be handed. The run is still
        # recorded: it happened, and what it could not settle is the result.
        return CouncilWithoutVector(
            advisory_id=finding.advisory.advisory_id,
            single_assessor=run.single_assessor,
            unresolved_metrics=unresolved,
            contested_metrics=contested,
            rulings=rulings,
        )
    return CouncilAssessment(
        advisory_id=finding.advisory.advisory_id,
        vector=str(agreed_vector(run.rulings, VECTOR_VERSION)),
        single_assessor=run.single_assessor,
        rulings=rulings,
    )


def metrics_of(run, kind) -> tuple[str, ...]:
    """Name the metrics a run left in one state, in specification order."""
    return tuple(
        metric for metric in METRIC_ORDER if isinstance(run.rulings.get(metric), kind)
    )


def watching(findings: tuple[Finding, ...], roster: Roster, out) -> CouncilProgress:
    """Count the calls this roster will make over the findings it can read."""
    # Only the findings that carry text and only the members that will be asked:
    # a total that counts calls nobody makes is a progress bar that never fills.
    readable = [one for one in findings if advisory_text(one)]
    return CouncilProgress(len(readable), len(members_to_ask(roster)), out)


def advisory_text(finding: Finding) -> str:
    """Give the text a member reads, which is the advisory's own description."""
    return finding.advisory.details.strip()
