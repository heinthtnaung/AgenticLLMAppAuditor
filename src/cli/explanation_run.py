"""Asking why the published sources differ, once per disputed finding, after the council.

**Only where the sources disagree, and only beside a council.** A finding whose
readable sources agree has nothing to explain and is recorded as such; a run
that asked for no council asks no model this either, and the record says so
(`report.absences`).

**After every call that produces a value.** The audit runs the council, and any
escalation, over every finding first, and only then asks for explanations
(`cli.audit`). So no explanation is asked before the values it sits beside are
fixed, and the explainer, one model, is loaded once rather than per finding.

**The explainer is the escalation model where one is named, otherwise the
council's first member that is not hosted** -- on this machine, or on the Ollama
server the members share. No setting chooses it, and the record names it. A
roster of hosted members only has nobody to explain with, and is refused.

**Nothing reads an explanation back.** It is carried beside the published
scores; the council's vector and the Organisation Risk Score never see it. And
`cli.council_run.assess_one`, the step the evaluation harness replays, never
asks for one, so every saved pass re-derives without it.
"""

from typing import Mapping

from cli.council_run import NO_TEXT_TO_READ, advisory_text
from cli.progress import NO_EXPLANATION_PROGRESS, ExplanationProgress
from council.explanation import DroppedItem, Explained, Explanation, explain
from council.providers import PROVIDER_CLIENTS, AskMember
from council.roster import Member, Roster, members_to_ask
from findings.finding import Finding
from report.explanation_record import (
    DroppedMetric,
    ExplainedMetric,
    ExplanationRecord,
    SourcesExplained,
    SourcesNotExplained,
)

NOT_DISPUTED = "no two of its readable sources disagree, so there is nothing to explain"
NO_LOCAL_EXPLAINER = (
    "no member to explain with that is not hosted: the explainer runs on the members' "
    "Ollama server, and no escalation model is named"
)


def explainer_of(roster: Roster, escalation: Member | None) -> Member:
    """Give the model that explains: the escalation model if named, else the first not hosted."""
    if escalation is not None:
        return escalation
    unhosted = [one for one in members_to_ask(roster) if not one.is_hosted()]
    if not unhosted:
        raise ValueError(NO_LOCAL_EXPLAINER)
    return unhosted[0]


def explanations(
    findings: tuple[Finding, ...], explainer: Member,
    clients=PROVIDER_CLIENTS, progress=NO_EXPLANATION_PROGRESS,
) -> tuple[ExplanationRecord, ...]:
    """Explain every disputed finding, and record why each of the others was not explained."""
    return tuple(explanation_of(one, explainer, clients, progress) for one in findings)


def to_explain(findings: tuple[Finding, ...]) -> tuple[Finding, ...]:
    """Give the findings a model will be asked about: sources that disagree, and text to read."""
    return tuple(one for one in findings if one.disputed_metrics() and advisory_text(one))


def explaining(findings: tuple[Finding, ...], out) -> ExplanationProgress:
    """Count the explanation calls a run will make, for its progress lines."""
    return ExplanationProgress(len(to_explain(findings)), out)


def explanation_of(
    finding: Finding, explainer: Member, clients: Mapping[str, AskMember], progress
) -> ExplanationRecord:
    """Ask why one finding's sources differ, or record why it is not asked."""
    advisory_id = finding.advisory.advisory_id
    if not finding.disputed_metrics():
        return SourcesNotExplained(advisory_id, NOT_DISPUTED)
    if not advisory_text(finding):
        return SourcesNotExplained(advisory_id, NO_TEXT_TO_READ)
    progress.explaining(advisory_id, explainer.name)
    said = explain(advisory_text(finding), published_on(finding), explainer, clients)
    return record_of(advisory_id, said)


def published_on(finding: Finding) -> dict[str, dict[str, str]]:
    """Give each source's value on each disputed metric, and nothing of those they agree on."""
    return {metric: values_on(finding, metric) for metric in finding.disputed_metrics()}


def values_on(finding: Finding, metric: str) -> dict[str, str]:
    """Give what each readable source published for one metric."""
    return {score.source: score.parsed_vector.metrics[metric] for score in finding.scores}


def record_of(advisory_id: str, said: Explanation) -> ExplanationRecord:
    """Put what the explainer gave into the report's terms, what it did not keep included."""
    dropped = tuple(dropped_of(one) for one in said.dropped)
    if not isinstance(said, Explained):
        because = f"{said.model}: {said.because}"
        return SourcesNotExplained(
            advisory_id, because, dropped, model=said.model, prompt_version=said.prompt_version
        )
    # Verified, every one: `council.explanation` keeps no item whose quotation is not in the text.
    items = tuple(ExplainedMetric(one.metric, one.why, one.quotation, True) for one in said.items)
    return SourcesExplained(advisory_id, said.model, said.prompt_version, items, dropped)


def dropped_of(dropped: DroppedItem) -> DroppedMetric:
    """Put one item that was not kept into the report's terms, with its reason."""
    said = dropped.item
    found, reason = dropped.quotation_found, dropped.reason
    return DroppedMetric(said.metric, said.why, said.quotation, found, reason)
