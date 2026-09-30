"""Sending the metrics a council left open to one larger local model, in both orders.

**The trigger is what the order-checked council could not settle**: a metric
still contested or unresolved once every member has read it both ways. Nothing
else is sent -- not a settled metric, and never the whole advisory -- and the
reply is worth only what `chairman.rule_on_escalation` says it is. This file
asks; the chairman decides.

**Asked in both orders, like every member.** The escalation model reads each
open metric with the options in order and reversed, and its two readings become
one reply by the members' own rule (`council.order_check`), so a positional
answer settles nothing here either.

**One model, on this machine, and not a member.** The model is named by
`AUDITOR_ESCALATION_MODEL` and runs on the local Ollama server; a hosted one, or
one already on the council, is refused before anything is asked. A council
member escalating to itself would read the same prompt again and count twice.

**The trigger has a precondition for a contest: two or more members that can
contest something between themselves.** A contest requires two distinct
*verified* values (`ruling.ContestedMetric`), so one member asked alone can only
settle or leave unresolved, and every metric it settles alone is agreement
nobody cross-checked, which no escalation will ever see. Measured on the CPU full
run in `measurements/council_runs/`, Qwen (`qwen2.5:7b-instruct`) beside Gemma
(`gemma4:latest`): 61 of 144 metrics came out contested because the second
member disagreed, and a one-member council would have recorded all 61 as settled.
`single_assessor` counts the members reached, so it would say so of the run; the
`SOLE` basis on each metric settled by one member's quotation alone says so of
the metric.

That holds for a trigger on what members reply, not for escalation in general. A
trigger on the finding's `disputed_metrics()` -- which `cli.council_run` already
reads to scope a run, and which no member's reply changes -- would reach the
escalation model even from a one-member council. That is a different policy.
"""

from dataclasses import replace
from typing import Callable, Mapping

from council.chairman import rule_on_escalation
from council.order_check import reconciled
from council.prompt import build_prompt
from council.providers import AskMember
from council.roster import Member
from council.ruling import SettledMetric
from council.run import CouncilRun, MetricEscalation, MetricRound, OrderReadings
from council.runner import ask_one_member, nobody_asking


def escalate(
    run: CouncilRun, advisory_text: str, escalation: Member | None,
    clients: Mapping[str, AskMember], asking: Callable[[str, str, bool], None] = nobody_asking,
) -> CouncilRun:
    """Put every metric the council left open to the escalation model; with none, change nothing."""
    if escalation is None:
        return run
    refuse_unfit_escalation(escalation, run.asked, clients)
    rounds = [escalated(one, advisory_text, escalation, clients, asking) for one in run.rounds]
    return replace(run, rounds=tuple(rounds))


def escalated(
    round_: MetricRound, advisory_text: str, escalation: Member,
    clients: Mapping[str, AskMember], asking: Callable[[str, str, bool], None],
) -> MetricRound:
    """Leave a settled metric as it is, and put an open one to the escalation model."""
    if isinstance(round_.ruling, SettledMetric):
        return round_
    in_order = build_prompt(round_.metric, advisory_text)
    reversed_order = build_prompt(round_.metric, advisory_text, reversed_options=True)
    readings = OrderReadings(
        ask_one_member(escalation, in_order, clients, asking),
        ask_one_member(escalation, reversed_order, clients, asking, reversed_options=True),
    )
    reply = reconciled(readings.in_order, readings.reversed_order)
    # The redacted text, which is what the model read and so what its quotation must be in.
    ruling = rule_on_escalation(round_.ruling, reply, in_order.advisory_shown)
    asked = MetricEscalation(round_.ruling, reply, readings)
    return replace(round_, ruling=ruling, escalation=asked)


def refuse_unfit_escalation(
    escalation: Member | None, council: tuple[str, ...], clients: Mapping[str, AskMember]
) -> None:
    """Refuse an escalation model that is hosted, sits on the council, or has no client here."""
    if escalation is None:
        return
    if not escalation.runs_local:
        raise ValueError(f"{escalation.name} is hosted; the escalation model runs on this machine")
    if escalation.name in council:
        raise ValueError(
            f"{escalation.name} is on the council, so it cannot also be the model "
            "the council's open metrics escalate to"
        )
    if escalation.provider not in clients:
        raise ValueError(
            f"no client for provider {escalation.provider!r} reaches {escalation.name}"
        )
